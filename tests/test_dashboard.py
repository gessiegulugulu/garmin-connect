"""Regression checks for date windows, real-data aggregation, and plan precedence."""

import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_sport_page import (average, build_dashboard, chart, future_sessions,
                             load_week, render_insights, render_metrics, row_date)
from sync_garmin_data import fetch_week, normalize_activity, normalize_day


TABLE = "| 日期 | 场地 | 训练 | 具体内容 | 强度 | 状态 |\n|---|---|---|---|---|---|\n"


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.today = date(2026, 10, 23)

    def write_data(self, **changes):
        payload = {
            "schema_version": 1, "timezone": "Asia/Shanghai",
            "period_start": "2026-10-16", "period_end": "2026-10-22",
            "days": [], "activities": [], **changes,
        }
        path = self.root / "week.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_only_last_seven_complete_days_are_used(self):
        path = self.write_data(days=[
            {"date": "2026-10-15", "steps": 99999},
            {"date": "2026-10-16", "steps": 1200},
            {"date": "2026-10-22", "steps": 3600},
            {"date": "2026-10-23", "steps": 88888},
        ], activities=[{"start": "2026-10-15 10:00:00"}, {"start": "2026-10-22 10:00:00"}])
        days, activities, _ = load_week(path, self.today)
        self.assertEqual([row["date"] for row in days], [(self.today - timedelta(days=i)).isoformat() for i in range(7, 0, -1)])
        self.assertEqual(average(days, "steps"), 2400)
        self.assertEqual(len(activities), 1)

    def test_stale_activity_export_is_not_reported_as_zero(self):
        path = self.write_data(period_start="2026-10-15", period_end="2026-10-21")
        days, activities, _ = load_week(path, self.today)
        self.assertEqual(len(days), 7)
        self.assertIsNone(activities)

    def test_empty_successful_activity_export_is_zero(self):
        _, activities, _ = load_week(self.write_data(), self.today)
        self.assertEqual(activities, [])

    def test_missing_export_produces_explicit_empty_states(self):
        plan = self.root / "TRAINING_PLAN.md"
        plan.write_text("# 计划\n", encoding="utf-8")
        result = build_dashboard(plan, self.root / "missing.json", self.today)
        self.assertIn("本周暂无记录", result)
        self.assertIn("本周活动记录尚未同步", result)
        self.assertEqual(result.count('class="session unscheduled"'), 7)

    def test_missing_values_are_excluded_but_measured_zero_is_kept(self):
        self.assertEqual(average([{"stress": 0}, {"stress": 30}, {"stress": None}, {"stress": -1}], "stress"), 15)
        self.assertIsNone(average([{}, {"stress": None}], "stress"))

    def test_nan_and_booleans_cannot_become_metrics(self):
        self.assertEqual(average([{"steps": float("nan")}, {"steps": True}, {"steps": 20}], "steps"), 20)

    def test_future_plan_merges_monthly_and_daily_overrides(self):
        plan = "2026-10-21 至 2026-10-27\n" + TABLE + "| 10-23 周五 | — | 休息 | 晚上不运动 | — | 休息 |\n"
        monthly = "2026-10-21 至 2026-11-20\n" + TABLE + (
            "| 10-22 周四 | 户外 | 旧计划 | 不能显示 | 3 | 计划 |\n"
            "| 10-23 周五 | 户外 | 月度跑步 | 被七日计划覆盖 | 3 | 计划 |\n"
            "| 10-29 周四 | 户外 | 连续轻松跑 | 跑20分钟 | 3-4 | 计划 |\n")
        sessions = future_sessions(plan, monthly, self.today)
        self.assertEqual(len(sessions), 7)
        self.assertEqual(sessions[0]["row"][2], "休息")
        self.assertEqual(sessions[-1]["row"][2], "连续轻松跑")
        self.assertIsNone(sessions[1]["row"])
        self.assertEqual(sessions[-1]["source"], "月度安排")

    def test_plan_dates_roll_over_new_year(self):
        today = date(2026, 12, 30)
        monthly = "2026-12-28 至 2027-01-27\n" + TABLE + "| 01-02 周六 | 球场 | 网球 | 10:00开始 | 4 | 计划 |\n"
        sessions = future_sessions("", monthly, today)
        self.assertEqual(sessions[3]["date"], date(2027, 1, 2))
        self.assertEqual(sessions[3]["row"][2], "网球")
        self.assertIsNone(row_date("02-30 周二", today))

    def test_expired_plans_are_not_repeated(self):
        old_plan = "2026-06-05 至 2026-06-11\n" + TABLE + "| 06-05 周五 | 户外 | 跑步 | 旧计划 | 3 | 计划 |\n"
        self.assertTrue(all(session["row"] is None for session in future_sessions(old_plan, "", self.today)))

    def test_missing_nights_do_not_inflate_hrv_balance_count(self):
        days = [{"date": "2026-10-16", "hrv": 50, "hrv_status": "BALANCED"},
                {"date": "2026-10-17", "hrv": None, "hrv_status": "BALANCED"}]
        self.assertIn("平衡 1 天", render_metrics(days))
        self.assertIn("标记平衡 1 天", render_insights(days, []))

    def test_chart_does_not_connect_across_missing_days(self):
        days = [{"date": "2026-10-16", "hrv": 40}, {"date": "2026-10-17"}, {"date": "2026-10-18", "hrv": 50}]
        result = chart(days, "hrv", "HRV", "ms")
        self.assertEqual(result.count('<polyline class="chart-line"'), 2)
        self.assertIn("chart-missing", result)

    def test_plan_content_is_escaped(self):
        plan = self.root / "TRAINING_PLAN.md"
        plan.write_text("2026-10-23\n" + TABLE + '| 10-23 周五 | <img src=x> | <script>alert(1)</script> | <b>内容</b> | 3 | 计划 |\n', encoding="utf-8")
        result = build_dashboard(plan, self.write_data(), self.today)
        self.assertNotIn("<script>", result)
        self.assertIn("&lt;script&gt;", result)
        self.assertNotIn("<img src=x>", result)


class GarminExportTests(unittest.TestCase):
    def test_sleep_uses_sleep_summary_instead_of_daily_stats(self):
        row = normalize_day("2026-10-22", {"sleepingSeconds": 100, "includesWellnessData": True},
                            {"dailySleepDTO": {"sleepTimeSeconds": 25200}}, {}, {})
        self.assertEqual(row["sleep_hours"], 7)

    def test_absent_sleep_and_wellness_are_not_zero(self):
        row = normalize_day("2026-10-22", {"totalSteps": 0, "includesWellnessData": False},
                            {"dailySleepDTO": {"sleepTimeSeconds": 0}}, {}, {})
        self.assertIsNone(row["sleep_hours"])
        self.assertIsNone(row["steps"])

    def test_hrv_uses_each_night_rather_than_overlapping_weekly_means(self):
        row = normalize_day("2026-10-22", {}, {}, {"hrvSummary": {"weeklyAvg": 48, "lastNightAvg": 53}}, {})
        self.assertEqual(row["hrv"], 53)

    def test_waking_and_sleeping_respiration_are_kept_separate(self):
        row = normalize_day("2026-10-22", {}, {}, {},
                            {"avgWakingRespirationValue": 17, "avgSleepRespirationValue": 14})
        self.assertEqual(row["respiration"], 17)
        self.assertEqual(row["respiration_sleep"], 14)

    def test_respiration_fallback_requires_wellness_coverage(self):
        covered = {"includesWellnessData": True, "avgWakingRespirationValue": 16}
        row = normalize_day("2026-10-22", covered, {}, {}, {})
        self.assertEqual(row["respiration"], 16)
        missing = normalize_day("2026-10-22", {**covered, "includesWellnessData": False}, {}, {}, {})
        self.assertIsNone(missing["respiration"])
        self.assertIsNone(missing["respiration_sleep"])

    def test_missing_respiration_does_not_become_zero_breaths(self):
        row = normalize_day("2026-10-22", {}, {}, {},
                            {"avgWakingRespirationValue": 0, "avgSleepRespirationValue": -1})
        self.assertIsNone(row["respiration"])
        self.assertIsNone(row["respiration_sleep"])

    def test_export_excludes_identity_and_location(self):
        row = normalize_activity({"startTimeLocal": "2026-10-21 18:59:00", "activityName": "Home address",
                                  "activityId": 123, "startLatitude": 31, "userProfileId": 99,
                                  "activityType": {"typeKey": "tennis_v2"}, "duration": 3600})
        self.assertEqual(set(row), {"start", "type", "duration_minutes", "distance_km", "average_hr"})
        self.assertEqual(row["duration_minutes"], 60)

    def test_total_fetch_failure_does_not_publish_zero_data(self):
        class UnavailableAPI:
            def __getattr__(self, method):
                def unavailable(*args):
                    if method == "get_activities_by_date":
                        return []
                    raise RuntimeError("do not expose authentication details")
                return unavailable

        with self.assertRaisesRegex(RuntimeError, "previous export was preserved"):
            fetch_week(UnavailableAPI(), date(2026, 10, 23))


if __name__ == "__main__":
    unittest.main()
