#!/usr/bin/env python3
"""Build a self-contained weekly health dashboard for Hugo or local preview."""

from __future__ import annotations

import argparse
import html
import json
import math
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path


def render_inline(text: str) -> str:
    """Render a safe subset of inline Markdown."""
    escaped = html.escape(text, quote=True)
    code_fragments: list[str] = []

    def stash_code(match: re.Match[str]) -> str:
        code_fragments.append(f"<code>{match.group(1)}</code>")
        return f"\x00CODE{len(code_fragments) - 1}\x00"

    escaped = re.sub(r"`([^`]+)`", stash_code, escaped)
    escaped = re.sub(
        r"\[([^\]]+)\]\(MONTHLY_ROUTINE\.md\)",
        r'<a href="#monthly">\1</a>',
        escaped,
    )
    escaped = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        r'<a href="\2" rel="noopener noreferrer">\1</a>',
        escaped,
    )
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)

    for index, fragment in enumerate(code_fragments):
        escaped = escaped.replace(f"\x00CODE{index}\x00", fragment)
    return escaped


def is_table_separator(line: str) -> bool:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def render_markdown(markdown: str) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    paragraph: list[str] = []
    in_list = False
    index = 0

    def flush_paragraph() -> None:
        if paragraph:
            output.append(f"<p>{'<br>'.join(render_inline(line) for line in paragraph)}</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            output.append("</ul>")
            in_list = False

    while index < len(lines):
        line = lines[index].rstrip()

        if line.startswith("|") and index + 1 < len(lines) and is_table_separator(lines[index + 1]):
            flush_paragraph()
            close_list()
            headers = split_table_row(line)
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].lstrip().startswith("|"):
                rows.append(split_table_row(lines[index]))
                index += 1

            output.append('<div class="table-wrap"><table><thead><tr>')
            output.extend(f"<th>{render_inline(cell)}</th>" for cell in headers)
            output.append("</tr></thead><tbody>")
            for row in rows:
                output.append("<tr>")
                output.extend(f"<td>{render_inline(cell)}</td>" for cell in row)
                output.append("</tr>")
            output.append("</tbody></table></div>")
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            flush_paragraph()
            close_list()
            level = min(len(heading.group(1)) + 1, 6)
            output.append(f"<h{level}>{render_inline(heading.group(2))}</h{level}>")
        elif re.match(r"^\s*[-*]\s+", line):
            flush_paragraph()
            if not in_list:
                output.append("<ul>")
                in_list = True
            item = re.sub(r"^\s*[-*]\s+", "", line)
            output.append(f"<li>{render_inline(item)}</li>")
        elif not line.strip():
            flush_paragraph()
            close_list()
        elif re.fullmatch(r"\s*([-*_])\1{2,}\s*", line):
            flush_paragraph()
            close_list()
            output.append("<hr>")
        else:
            close_list()
            paragraph.append(line.strip())
        index += 1

    flush_paragraph()
    close_list()
    return "\n".join(output)


def extract_tables(markdown: str) -> list[tuple[list[str], list[list[str]]]]:
    lines = markdown.splitlines()
    tables = []
    for index, line in enumerate(lines[:-1]):
        if line.startswith("|") and is_table_separator(lines[index + 1]):
            rows = []
            for row in lines[index + 2:]:
                if not row.startswith("|"):
                    break
                rows.append(split_table_row(row))
            tables.append((split_table_row(line), rows))
    return tables


def session_kind(title: str, status: str) -> str:
    if status == "休息":
        return "rest"
    if "网球" in title:
        return "tennis"
    if "跑" in title:
        return "run"
    if "步" in title or "徒步" in title:
        return "walk"
    return "strength"


SHANGHAI = ZoneInfo("Asia/Shanghai")
WEEKDAYS = "一二三四五六日"
ACTIVITY_NAMES = {
    "tennis": "网球", "tennis_v2": "网球", "hiking": "徒步", "walking": "步行", "running": "跑步",
    "treadmill_running": "跑步机", "strength_training": "力量训练",
    "indoor_cardio": "室内有氧", "cardio": "有氧训练", "cycling": "骑行",
    "lap_swimming": "泳池游泳", "swimming": "游泳", "yoga": "瑜伽",
    "elliptical": "椭圆机", "rowing": "划船", "other": "其他运动",
}
ICONS = {
    "leaf": '<path d="M20 4c-8-2-16 3-14 10s13 6 14-10Z"/><path d="M4 21 15 10"/>',
    "rest": '<path d="M20 15.5A8.5 8.5 0 0 1 8.5 4a8.5 8.5 0 1 0 11.5 11.5Z"/>',
    "tennis": '<circle cx="12" cy="12" r="8.5"/><path d="M5 6c6 1 6 11 14 12M5 18c7-1 6-11 14-12"/>',
    "run": '<circle cx="15" cy="4" r="1.5"/><path d="m10 10 3-4 3 5 4 1M4 10l5 1 4 5-3 6M13 12l-5 5H3"/>',
    "walk": '<circle cx="13" cy="4" r="1.5"/><path d="m8 11 4-4 3 5 4 2M12 8l-2 8-4 5M10 16l6 5"/>',
    "strength": '<path d="m6 6 12 12M4 9l5-5M15 20l5-5M2 7l5-5M17 22l5-5"/>',
    "calendar": '<rect x="4" y="5" width="16" height="16" rx="4"/><path d="M8 3v4m8-4v4M4 11h16m-11 4h.01m6 0h.01"/>',
    "heart": '<path d="M20 5c-3-3-7-1-8 1-1-2-5-4-8-1s-1 7 8 14c9-7 11-11 8-14Z"/>',
    "sleep": '<path d="M20 15.5A8.5 8.5 0 0 1 8.5 4a8.5 8.5 0 1 0 11.5 11.5Z"/>',
    "trend": '<path d="m4 16 6-6 4 4 6-9m-6 0h6v6"/>',
    "spark": '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z"/>',
    "arrow": '<path d="M7 17 17 7M7 7h10v10"/>',
    "chevron": '<path d="m9 5 7 7-7 7"/>',
    "battery": '<rect x="3" y="6" width="17" height="12" rx="3"/><path d="M23 10v4M7 10v4m4-4v4m4-4v4"/>',
    "breath": '<path d="M3 8h11a3 3 0 1 0-3-3M3 12h15a3 3 0 1 1-3 3M3 16h5a2 2 0 1 1-2 2"/>',
    "pulse": '<path d="M2 12h5l3-8 4 16 3-8h5"/>',
    "stress": '<path d="M4 18a8 8 0 1 1 16 0M12 15l4-6"/><circle cx="12" cy="16" r="1"/>',
    "steps": '<path d="M8 3c3 0 4 5 3 8s-5 3-6 0S5 3 8 3Zm8 8c3 0 4 5 3 8s-5 3-6 0 0-8 3-8Z"/>',
}


def icon(name: str, css: str = "") -> str:
    return (f'<svg class="icon {html.escape(css)}" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>')


def valid_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def values(days: list[dict], key: str) -> list[float]:
    return [row[key] for row in days if valid_number(row.get(key))]


def average(days: list[dict], key: str) -> float | None:
    measured = values(days, key)
    return sum(measured) / len(measured) if measured else None


def fmt(value: float | None, decimals: int = 0) -> str:
    return f'{value:,.{decimals}f}' if value is not None else "—"


def load_week(path: Path, today: date) -> tuple[list[dict], list[dict] | None, dict]:
    payload = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    if payload and (payload.get("schema_version") != 1 or payload.get("timezone") != "Asia/Shanghai"):
        raise ValueError("Unsupported Garmin export schema or timezone")
    dates = [(today - timedelta(days=offset)).isoformat() for offset in range(7, 0, -1)]
    by_date = {row["date"]: row for row in payload.get("days", []) if row.get("date") in dates}
    days = [by_date.get(day, {"date": day}) for day in dates]
    # Never turn an old or missing activities export into a claim of zero activities.
    complete_period = payload.get("period_start") == dates[0] and payload.get("period_end") == dates[-1]
    activities = [row for row in payload.get("activities", []) if row.get("start", "")[:10] in dates] if complete_period else None
    return days, activities, payload


def row_date(label: str, anchor: date) -> date | None:
    match = re.search(r"(?:(\d{4})-)?(\d{1,2})-(\d{1,2})", label)
    if not match:
        return None
    year, month, day = match.groups()
    candidates = []
    for candidate_year in [int(year)] if year else range(anchor.year - 1, anchor.year + 2):
        try:
            candidates.append(date(candidate_year, int(month), int(day)))
        except ValueError:
            continue
    return min(candidates, key=lambda item: abs((item - anchor).days)) if candidates else None


def document_anchor(markdown: str, fallback: date) -> date:
    match = re.search(r"\d{4}-\d{2}-\d{2}", markdown)
    return date.fromisoformat(match.group()) if match else fallback


def future_sessions(plan: str, monthly: str, today: date) -> list[dict]:
    by_date = {}
    # A specific seven-day plan overrides the monthly direction for the same date.
    for markdown, source in [(monthly, "月度安排"), (plan, "七日计划")]:
        anchor = document_anchor(markdown, today)
        for headers, rows in extract_tables(markdown):
            if headers[:2] != ["日期", "场地"]:
                continue
            for row in rows:
                if len(row) == 6 and (day := row_date(row[0], anchor)) is not None:
                    by_date[day] = {"date": day, "row": row, "source": source}
    return [by_date.get(day, {"date": day, "row": None, "source": None})
            for day in (today + timedelta(days=offset) for offset in range(7))]


def render_sessions(sessions: list[dict], today: date) -> str:
    cards = []
    for session in sessions:
        day, row = session["date"], session["row"]
        weekday = "今天" if day == today else "周" + WEEKDAYS[day.weekday()]
        date_html = f'<span class="session-date"><span>{weekday}</span><strong>{day:%m.%d}</strong></span>'
        if row is None:
            cards.append(f'<div class="session unscheduled">{date_html}<span class="session-symbol">{icon("calendar")}</span>'
                         '<span class="session-copy"><strong>待安排</strong><small>暂无已制定的计划</small></span></div>')
            continue
        _, location, title, detail, effort, status = row
        kind = session_kind(title, status)
        effort_label = effort if "RPE" in effort or effort in ("—", "轻松") else f"RPE {effort}"
        meta = " · ".join(part for part in [location if location != "—" else "", effort_label if effort_label != "—" else ""] if part)
        cards.append(
            f'<details class="session {kind}{" is-today" if day == today else ""}"><summary>'
            f'{date_html}<span class="session-symbol">{icon(kind)}</span>'
            f'<span class="session-copy"><strong>{html.escape(title)}</strong><small>{html.escape(meta or "留一点时间给恢复")}</small></span>'
            f'{icon("chevron", "session-chevron")}</summary>'
            f'<div class="session-body"><p>{render_inline(detail)}</p>'
            f'<small>{html.escape(session["source"])} · {html.escape(status)}</small></div></details>'
        )
    return "".join(cards)


def chart(days: list[dict], key: str, label: str, unit: str, kind: str = "line") -> str:
    measured = values(days, key)
    if not measured:
        return f'<div class="chart-empty">{icon("breath" if key == "respiration" else "pulse")}<span>本周暂无记录</span><small>有数据后显示 7 日趋势</small></div>'
    low, high = min(measured), max(measured)
    if kind == "bars":
        low, high = 0, max(high, 1)
    elif low == high:
        low, high = max(0, low - 1), high + 1
    padding = (high - low) * .2 if kind != "bars" else 0
    low, high = low - padding, high + padding
    points, segments, shapes = [], [], []
    for index, row in enumerate(days):
        value = row.get(key)
        x = 12 + index * 30
        label_text = html.escape(f'{row["date"]} · {label} {fmt(value, 1)} {unit}' if valid_number(value) else f'{row["date"]} · 暂无记录')
        if not valid_number(value):
            if points:
                segments.append(points)
                points = []
            shapes.append(f'<path class="chart-missing" d="M{x - 4} 69h8"><title>{label_text}</title></path>')
        else:
            y = 69 - (value - low) / (high - low) * 54
            if kind == "bars":
                shapes.append(f'<rect class="chart-bar" x="{x - 9}" y="{y:.2f}" width="18" height="{max(1, 70 - y):.2f}" rx="4"><title>{label_text}</title></rect>')
            else:
                points.append(f"{x},{y:.2f}")
                shapes.append(f'<circle class="chart-dot" cx="{x}" cy="{y:.2f}" r="3"><title>{label_text}</title></circle>')
        shapes.append(f'<text x="{x}" y="91" text-anchor="middle">{row["date"][-2:]}</text>')
    if points:
        segments.append(points)
    lines = ''.join(f'<polyline class="chart-line" points="{" ".join(segment)}"/>' for segment in segments)
    return (f'<svg class="trend-chart" viewBox="0 0 204 96" role="img" aria-label="{html.escape(label)}七日趋势；横轴为日期，缺失数据留空">'
            f'<title>{html.escape(label)} · 最近七日，点击卡片查看每日数值</title>'
            '<path class="chart-guide" d="M3 70h198M3 38h198"/>' + lines + ''.join(shapes) + '</svg>')


def gauge(value: float | None) -> str:
    if value is None:
        return '<div class="chart-empty"><span>本周暂无记录</span></div>'
    clipped = min(max(value, 0), 100)
    angle = math.pi * (1 - clipped / 100)
    x, y = 102 + 68 * math.cos(angle), 78 - 68 * math.sin(angle)
    return (f'<svg class="stress-gauge" viewBox="0 0 204 100" role="img" aria-label="周平均压力 {fmt(value)}，量表 0 至 100">'
            '<path class="gauge-track" d="M34 78a68 68 0 0 1 136 0" pathLength="100"/>'
            f'<path class="gauge-value" d="M34 78a68 68 0 0 1 136 0" pathLength="100" stroke-dasharray="{clipped:.2f} 100"/>'
            f'<circle class="gauge-dot" cx="{x:.2f}" cy="{y:.2f}" r="5"/>'
            '<text x="24" y="98">0</text><text x="160" y="98">100</text></svg>')


def metric_card(days: list[dict], *, key: str, name: str, symbol: str, theme: str,
                unit: str, description: str, note: str, decimals: int = 0,
                total: bool = False, kind: str = "line") -> str:
    measured = values(days, key)
    value = sum(measured) if total and measured else average(days, key)
    display = fmt(value, decimals)
    visual = gauge(value) if kind == "gauge" else chart(days, key, name, unit, kind)
    table_rows = ''.join(f'<tr><th scope="row">{row["date"][5:]}</th><td>{fmt(row.get(key) if valid_number(row.get(key)) else None, decimals)} {html.escape(unit)}</td></tr>' for row in days)
    return (f'<details class="metric {theme}" id="metric-{key}"><summary>'
            f'<span class="metric-heading"><span>{icon(symbol)}{name}</span>{icon("arrow", "metric-arrow")}</span>'
            f'<span class="metric-value{" compact" if len(display) > 5 else ""}">{display}</span>'
            f'<span class="metric-description">{html.escape(unit)} · {description}</span>'
            f'<span class="metric-visual">{visual}</span>'
            f'<span class="metric-footer"><span>{note}</span><small>{len(measured)}/7 天</small></span>'
            '</summary><div class="metric-detail"><table>'
            f'<caption>{name} · 每日记录（{html.escape(unit)}）</caption>'
            '<thead><tr><th scope="col">日期</th><th scope="col">数值</th></tr></thead>'
            f'<tbody>{table_rows}</tbody></table><p>仅统计有记录的日期；— 表示缺失。</p></div></details>')


def render_metrics(days: list[dict]) -> str:
    lows = average(days, "battery_low")
    sleep_score = average(days, "sleep_score")
    resting = average(days, "resting_hr")
    sleeping_respiration = average(days, "respiration_sleep")
    step_mean = average(days, "steps")
    balanced = sum(row.get("hrv_status") == "BALANCED" and valid_number(row.get("hrv")) for row in days)
    return ''.join([
        metric_card(days, key="battery_high", name="身体电量", symbol="battery", theme="mint",
                    unit="/ 100", description="每日最高值的周均值", note=f'最低值均值 {fmt(lows)}'),
        metric_card(days, key="respiration", name="呼吸", symbol="breath", theme="peach",
                    unit="次/分", description="清醒呼吸均值的周均值", decimals=1,
                    note=f'睡眠均值 {fmt(sleeping_respiration, 1)} 次/分'),
        metric_card(days, key="hrv", name="HRV", symbol="pulse", theme="lavender",
                    unit="ms", description="夜间均值的周均值", note=f'平衡 {balanced} 天' if values(days, "hrv") else "等待夜间记录", kind="bars"),
        metric_card(days, key="sleep_hours", name="睡眠", symbol="sleep", theme="lilac",
                    unit="小时", description="每晚平均睡眠", note=f'平均评分 {fmt(sleep_score)}', decimals=1, kind="bars"),
        metric_card(days, key="stress", name="压力", symbol="stress", theme="rose",
                    unit="/ 100", description="每日平均压力的周均值", note=f'静息心率均值 {fmt(resting)} bpm', kind="gauge"),
        metric_card(days, key="steps", name="活动", symbol="steps", theme="ice",
                    unit="步", description="本周累计步数", note=f'日均 {fmt(step_mean)} 步', total=True, kind="bars"),
    ])


def activity_title(activity: dict) -> str:
    return ACTIVITY_NAMES.get(activity.get("type"), "其他运动")


def activity_icon(activity: dict) -> str:
    title = activity_title(activity)
    return session_kind(title, "计划")


def render_activity_week(days: list[dict], activities: list[dict] | None) -> str:
    durations = {row["date"]: 0 for row in days}
    if activities is not None:
        for row in activities:
            durations[row["start"][:10]] += row.get("duration_minutes") or 0
    maximum = max(max(durations.values()), 1)
    bars = []
    for row in days:
        day = row["date"]
        duration = durations[day]
        description = f'{day} · {fmt(duration)} 分钟运动记录' if activities is not None else f'{day} · 活动记录未同步'
        bars.append(f'<div class="activity-day" title="{description}"><span class="activity-track"><span class="activity-fill" style="--bar-height:{duration / maximum * 100:.2f}%"></span></span>'
                    f'<span>{day[5:].replace("-", ".")}</span></div>')
    records = []
    for activity in activities or []:
        kind = activity_icon(activity)
        duration = fmt(activity.get("duration_minutes"))
        meta = f'{activity["start"][5:16].replace("T", " ")} · {duration} 分钟'
        if valid_number(activity.get("distance_km")) and activity["distance_km"] > 0:
            meta += f' · {fmt(activity["distance_km"], 2)} km'
        records.append(f'<li><span class="activity-symbol {kind}">{icon(kind)}</span><span><strong>{activity_title(activity)}</strong>'
                       f'<small>{html.escape(meta)}</small></span><span class="record-label">已记录</span></li>')
    if not records:
        message = "本周没有已记录的运动" if activities is not None else "本周活动记录尚未同步"
        records.append(f'<li class="empty-record">{message}</li>')
    total = sum(row.get("duration_minutes") or 0 for row in activities) if activities is not None else None
    count = str(len(activities)) if activities is not None else "—"
    return (f'<div class="panel-heading"><div><span class="eyebrow">YOUR WEEK IN MOTION</span><h2>这一周的活动</h2></div>{icon("trend")}</div>'
            f'<div class="activity-totals"><strong>{count}<small>次运动</small></strong><span>{fmt(total / 60 if total is not None else None, 1)}<small>小时记录时长</small></span></div>'
            f'<div class="activity-chart" role="group" aria-label="最近七日运动记录时长">{"".join(bars)}</div>'
            f'<ul class="activity-records">{"".join(records)}</ul><p class="panel-note">记录时长可能含休息；无记录不代表没有活动。</p>')


def render_insights(days: list[dict], activities: list[dict] | None) -> str:
    insights = []
    step_days = [row for row in days if valid_number(row.get("steps")) and valid_number(row.get("step_goal"))]
    if step_days:
        reached = sum(row["steps"] >= row["step_goal"] for row in step_days)
        insights.append(("trend", "mint", f'{reached} 天达到当日步数目标', f'共 {len(step_days)} 天有步数与目标记录'))
    if nights := values(days, "sleep_hours"):
        insights.append(("sleep", "lilac", f'每晚平均睡眠 {fmt(sum(nights) / len(nights), 1)} 小时',
                         f'共 {len(nights)} 晚 · 最短 {fmt(min(nights), 1)} / 最长 {fmt(max(nights), 1)} 小时'))
    if hrvs := values(days, "hrv"):
        balanced = sum(row.get("hrv_status") == "BALANCED" and valid_number(row.get("hrv")) for row in days)
        insights.append(("heart", "mint", f'夜间 HRV 平均 {fmt(sum(hrvs) / len(hrvs))} ms', f'共 {len(hrvs)} 晚有记录 · Garmin 标记平衡 {balanced} 天'))
    if heart_rates := values(days, "resting_hr"):
        insights.append(("pulse", "peach", f'静息心率平均 {fmt(sum(heart_rates) / len(heart_rates))} bpm', f'每日静息心率范围 {fmt(min(heart_rates))}—{fmt(max(heart_rates))} bpm'))
    missing_sleep = 7 - len(values(days, "sleep_hours"))
    if missing_sleep:
        insights.append(("calendar", "lavender", f'{missing_sleep} 晚睡眠记录缺失', '周均值只计算有记录的夜晚'))
    elif activities is not None:
        insights.append(("spark", "lavender", f'本周记录了 {len(activities)} 次运动', '运动记录与未来计划分别展示'))
    if not insights:
        return '<div class="empty-insights">同步本周数据后，变化会显示在这里。</div>'
    return '<ul class="insight-list">' + ''.join(
        f'<li><span class="insight-symbol {theme}">{icon(symbol)}</span><span><strong>{html.escape(title)}</strong><small>{html.escape(detail)}</small></span></li>'
        for symbol, theme, title, detail in insights) + '</ul>'


def sleep_target(monthly: str, today: date) -> str:
    anchor = document_anchor(monthly, today)
    for headers, rows in extract_tables(monthly):
        if headers[:2] != ["阶段", "日期"]:
            continue
        for row in rows:
            if len(row) != 5:
                continue
            labels = re.findall(r"(?:\d{4}-)?\d{2}-\d{2}", row[1])
            if len(labels) == 2:
                start, end = (row_date(label, anchor) for label in labels)
                if start is not None and end is not None and start <= today <= end:
                    return f'<div class="sleep-target">{icon("sleep")}<span><strong>本阶段作息目标</strong><small>{html.escape(row[2])} 起床 · {html.escape(row[3])} 关灯</small></span></div>'
    return ''


def build_dashboard(plan_path: Path, data_path: Path, today: date) -> str:
    plan = plan_path.read_text(encoding="utf-8")
    monthly_path = plan_path.parent / "MONTHLY_ROUTINE.md"
    monthly = monthly_path.read_text(encoding="utf-8") if monthly_path.is_file() else ""
    days, activities, payload = load_week(data_path, today)
    sessions = future_sessions(plan, monthly, today)
    start, end = date.fromisoformat(days[0]["date"]), date.fromisoformat(days[-1]["date"])
    period = f'{start:%Y.%m.%d} — {end:%m.%d}'
    future_end = today + timedelta(days=6)
    fetched = payload.get("fetched_at")
    try:
        updated = datetime.fromisoformat(fetched).astimezone(SHANGHAI).strftime("%m.%d %H:%M") if fetched else "尚未同步"
    except (ValueError, TypeError):
        updated = "时间未知"
    current_export = payload.get("period_start") == days[0]["date"] and payload.get("period_end") == days[-1]["date"]
    availability = "本周数据已同步" if current_export and not payload.get("missing_requests") else "部分数据待同步"
    style = (Path(__file__).parent / "sport_dashboard.css").read_text(encoding="utf-8")
    return f'''<style>{style}</style>
<div class="sport-dashboard" role="region" aria-label="个人健康周报">
  <header class="dashboard-header">
    <div class="greeting"><p>你好，</p><h1>保持自己的节奏<span>。</span></h1><p class="header-description">这里是你最近一周的健康概况</p></div>
    <div class="header-meta"><span class="today-label">{today:%Y 年 %m 月 %d 日} · 周{WEEKDAYS[today.weekday()]}</span><span class="period-pill">{icon("calendar")}<span>{period}<small>最近 7 个完整日 · 上海时间</small></span></span><span class="sync-status"><i></i>{availability}</span></div>
  </header>
  <div class="dashboard-grid">
    <section class="plan-panel glass" id="plan" aria-labelledby="plan-title">
      <div class="panel-heading"><div><span class="eyebrow">A LITTLE EVERY DAY</span><h2 id="plan-title">接下来 7 天</h2></div><span class="plan-count">7 <small>DAYS</small></span></div>
      <p class="plan-period">{today:%m.%d} — {future_end:%m.%d} <span>· 点击查看训练内容</span></p>
      <div class="sessions">{render_sessions(sessions, today)}</div>
      {sleep_target(monthly, today)}
      <p class="panel-note">以已制定的计划为准，随恢复状态调整。</p>
    </section>
    <section class="metrics-grid" aria-label="最近七日健康指标">{render_metrics(days)}</section>
    <section class="activity-panel glass" aria-label="最近七日运动记录">{render_activity_week(days, activities)}</section>
    <section class="insights-panel glass" aria-labelledby="insights-title"><div class="panel-heading"><div><span class="eyebrow">SMALL SIGNS, BIG PICTURE</span><h2 id="insights-title">一周里的小变化</h2></div>{icon("spark")}</div>{render_insights(days, activities)}<p class="panel-note">来自这一周的真实记录，留意长期的节奏。</p></section>
  </div>
  <footer class="dashboard-footer"><span>{icon("leaf")} 好好运动，也好好休息。</span><span>Garmin 数据 · 同步于 {html.escape(updated)} · 上海时间</span></footer>
</div>'''


def build_page(plan_path: Path, history_dir: Path, data_path: Path | None = None, today: date | None = None) -> str:
    # Keep the existing callable and --history argument compatible with automation.
    today = today or datetime.now(SHANGHAI).date()
    data_path = data_path or plan_path.parent / "data/garmin-week.json"
    return '''---
title: 健康与运动
url: /sport/
summary: 最近一周的健康概况与接下来七天的运动计划
hideMeta: true
ShowBreadCrumbs: false
ShowReadingTime: false
ShowShareButtons: false
ShowPostNavLinks: false
ShowToc: false
disableShare: true
---

''' + build_dashboard(plan_path, data_path, today) + '\n'


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=Path("TRAINING_PLAN.md"))
    parser.add_argument("--history", type=Path, default=Path("history"))
    parser.add_argument("--output", type=Path, default=Path("dist/sport.md"))
    parser.add_argument("--data", type=Path, default=Path("data/garmin-week.json"))
    parser.add_argument("--date", type=date.fromisoformat, default=datetime.now(SHANGHAI).date())
    parser.add_argument("--standalone", action="store_true", help="Build a complete HTML document for local preview")
    args = parser.parse_args()

    if not args.plan.is_file():
        raise SystemExit(f"Training plan not found: {args.plan}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.standalone:
        dashboard = build_dashboard(args.plan, args.data, args.date)
        page = ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1">'
                '<meta name="color-scheme" content="light"><title>健康与运动</title>'
                '</head><body>' + dashboard + '</body></html>')
    else:
        page = build_page(args.plan, args.history, args.data, args.date)
    args.output.write_text(page, encoding="utf-8")
    print(f"Built {args.output}")


if __name__ == "__main__":
    main()
