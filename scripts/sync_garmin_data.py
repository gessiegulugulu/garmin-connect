#!/usr/bin/env python3
"""Export only dashboard metrics for the last seven complete Shanghai days.

Authentication uses an existing token file or GARMIN_TOKENS_JSON. Credentials,
profile identifiers, GPS tracks, and raw API responses never enter the export.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")


def number(value: object, *, positive: bool = False) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    if not math.isfinite(value) or value < 0 or (positive and value == 0):
        return None
    return value


def normalize_day(day: str, stats: dict, sleep: dict, hrv: dict, respiration: dict) -> dict:
    # A day without wellness coverage must not become a zero-step day.
    covered = stats.get("includesWellnessData") is True
    dto = sleep.get("dailySleepDTO") or {}
    summary = hrv.get("hrvSummary") or {}
    sleep_seconds = number(dto.get("sleepTimeSeconds"), positive=True)
    scores = dto.get("sleepScores") or {}
    return {
        "date": day,
        "steps": number(stats.get("totalSteps")) if covered else None,
        "step_goal": number(stats.get("dailyStepGoal"), positive=True) if covered else None,
        "distance_km": number(stats.get("totalDistanceMeters")) / 1000
        if covered and number(stats.get("totalDistanceMeters")) is not None else None,
        "resting_hr": number(stats.get("restingHeartRate"), positive=True) if covered else None,
        "stress": number(stats.get("averageStressLevel")) if covered else None,
        "battery_high": number(stats.get("bodyBatteryHighestValue"), positive=True) if covered else None,
        "battery_low": number(stats.get("bodyBatteryLowestValue")) if covered else None,
        "respiration": number(respiration.get("avgWakingRespirationValue"), positive=True)
        or (number(stats.get("avgWakingRespirationValue"), positive=True) if covered else None),
        "respiration_sleep": number(respiration.get("avgSleepRespirationValue"), positive=True),
        "hrv": number(summary.get("lastNightAvg"), positive=True),
        "hrv_status": summary.get("status"),
        "sleep_hours": round(sleep_seconds / 3600, 4) if sleep_seconds else None,
        "sleep_score": number((scores.get("overall") or {}).get("value")) if sleep_seconds else None,
        "sleep_deep_minutes": number(dto.get("deepSleepSeconds")) / 60
        if sleep_seconds and number(dto.get("deepSleepSeconds")) is not None else None,
        "sleep_light_minutes": number(dto.get("lightSleepSeconds")) / 60
        if sleep_seconds and number(dto.get("lightSleepSeconds")) is not None else None,
        "sleep_rem_minutes": number(dto.get("remSleepSeconds")) / 60
        if sleep_seconds and number(dto.get("remSleepSeconds")) is not None else None,
    }


def normalize_activity(activity: dict) -> dict | None:
    start = activity.get("startTimeLocal")
    if not isinstance(start, str):
        return None
    # Use activity types rather than user-entered names, which may contain locations.
    kind = (activity.get("activityType") or {}).get("typeKey", "other")
    distance = number(activity.get("distance"))
    return {
        "start": start,
        "type": kind,
        "duration_minutes": (number(activity.get("duration")) or 0) / 60,
        "distance_km": distance / 1000 if distance is not None else None,
        "average_hr": number(activity.get("averageHR"), positive=True),
    }


def fetch_week(api: object, today: date) -> dict:
    dates = [today - timedelta(days=offset) for offset in range(7, 0, -1)]
    errors = []

    def fetch(method: str, day: str) -> dict:
        try:
            result = getattr(api, method)(day)
            return result if isinstance(result, dict) else {}
        except Exception:
            # Exception strings can contain request headers or account identifiers.
            errors.append({"date": day, "source": method})
            return {}

    days = []
    for day in dates:
        label = day.isoformat()
        days.append(normalize_day(label, fetch("get_stats", label),
                                  fetch("get_sleep_data", label),
                                  fetch("get_hrv_data", label),
                                  fetch("get_respiration_data", label)))
    # A failed activity query is different from a successful empty list.
    activities = api.get_activities_by_date(dates[0].isoformat(), dates[-1].isoformat())
    if not any(any(row.get(key) is not None for key in ("steps", "sleep_hours", "hrv")) for row in days):
        raise RuntimeError("No usable Garmin metrics; the previous export was preserved.")
    normalized = [item for raw in activities if (item := normalize_activity(raw)) is not None]
    normalized = [item for item in normalized if dates[0].isoformat() <= item["start"][:10] <= dates[-1].isoformat()]
    return {
        "schema_version": 1,
        "timezone": "Asia/Shanghai",
        "fetched_at": datetime.now(SHANGHAI).isoformat(timespec="minutes"),
        "period_start": dates[0].isoformat(),
        "period_end": dates[-1].isoformat(),
        "days": days,
        "activities": sorted(normalized, key=lambda item: item["start"], reverse=True),
        "missing_requests": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=date.fromisoformat, default=datetime.now(SHANGHAI).date())
    parser.add_argument("--output", type=Path, default=Path("data/garmin-week.json"))
    parser.add_argument("--token-store", type=Path, default=Path("~/.garminconnect").expanduser())
    args = parser.parse_args()
    from garminconnect import Garmin

    # Work on a temporary copy: refreshing a session never modifies the local login.
    with tempfile.TemporaryDirectory(prefix="garmin-dashboard-auth-") as folder:
        token_path = Path(folder) / "garmin_tokens.json"
        if token_json := os.environ.get("GARMIN_TOKENS_JSON"):
            json.loads(token_json)  # Reject malformed input before authentication.
            token_path.write_text(token_json, encoding="utf-8")
            token_path.chmod(0o600)
        else:
            source = args.token_store
            if source.is_dir():
                source /= "garmin_tokens.json"
            shutil.copyfile(source, token_path)
            token_path.chmod(0o600)
        api = Garmin(is_cn=os.environ.get("GARMIN_IS_CN", "false").lower() in ("true", "1", "yes"))
        api.login(folder)
        data = fetch_week(api, args.date)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(f"Synced {data['period_start']} through {data['period_end']}: "
          f"{len(data['activities'])} activities, {len(data['missing_requests'])} unavailable requests.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Garmin sync failed ({type(exc).__name__}); no credentials were logged.", file=sys.stderr)
        raise SystemExit(1) from None
