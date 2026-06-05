#!/usr/bin/env python3
"""Build a standalone sport dashboard from the training plan and history."""

from __future__ import annotations

import argparse
import html
import re
from datetime import datetime, timezone
from pathlib import Path


def render_inline(text: str) -> str:
    escaped = html.escape(text, quote=True)
    code_fragments: list[str] = []

    def stash_code(match: re.Match[str]) -> str:
        code_fragments.append(f"<code>{match.group(1)}</code>")
        return f"\x00CODE{len(code_fragments) - 1}\x00"

    escaped = re.sub(r"`([^`]+)`", stash_code, escaped)
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


def build_page(plan_path: Path, history_dir: Path) -> str:
    history_files = sorted(history_dir.rglob("*.md"), reverse=True)
    plan_html = render_markdown(plan_path.read_text(encoding="utf-8"))
    history_sections = []

    for position, path in enumerate(history_files):
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", path.stem)
        title = f"{date_match.group(1)} 周复盘" if date_match else path.stem.replace("-", " ")
        body = render_markdown(path.read_text(encoding="utf-8"))
        open_attribute = " open" if position == 0 else ""
        history_sections.append(
            f'<details class="sport-history-item"{open_attribute}>'
            f"<summary>{html.escape(title)}</summary>"
            f'<div class="sport-markdown-body">{body}</div>'
            "</details>"
        )

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    history_html = "\n".join(history_sections) or "<p>暂无历史复盘。</p>"

    return f"""---
title: 训练计划与复盘
url: /sport/
summary: Garmin 训练计划与每周复盘
---

<style>
  .sport-dashboard {{
    margin-top: 1.5rem;
  }}

  .sport-dashboard .sport-meta {{
    color: var(--secondary);
    font-size: 0.9rem;
    margin-bottom: 1.5rem;
  }}

  .sport-dashboard .sport-nav {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    margin: 1.2rem 0 2rem;
  }}

  .sport-dashboard .sport-nav a {{
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 0.35rem 0.8rem;
    text-decoration: none;
    font-size: 0.9rem;
  }}

  .sport-dashboard .sport-card {{
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.2rem;
    margin: 1.2rem 0;
    background: var(--entry);
  }}

  .sport-dashboard h2,
  .sport-dashboard h3,
  .sport-dashboard h4,
  .sport-dashboard h5,
  .sport-dashboard h6 {{
    margin-top: 1.6em;
  }}

  .sport-dashboard .table-wrap {{
    overflow-x: auto;
    margin: 1rem 0;
  }}

  .sport-dashboard table {{
    width: 100%;
    border-collapse: collapse;
    min-width: 720px;
    font-size: 0.95rem;
  }}

  .sport-dashboard th,
  .sport-dashboard td {{
    border-bottom: 1px solid var(--border);
    padding: 0.65rem 0.75rem;
    text-align: left;
    vertical-align: top;
  }}

  .sport-dashboard th {{
    background: var(--code-bg);
    font-weight: 700;
  }}

  .sport-dashboard code {{
    background: var(--code-bg);
    border-radius: 4px;
    padding: 0.1em 0.35em;
  }}

  .sport-dashboard details {{
    border-top: 1px solid var(--border);
  }}

  .sport-dashboard details:first-of-type {{
    border-top: 0;
  }}

  .sport-dashboard summary {{
    cursor: pointer;
    padding: 1rem 0;
    font-weight: 700;
  }}

  .sport-dashboard .sport-markdown-body {{
    padding-bottom: 1.2rem;
  }}
</style>

<div class="sport-dashboard">
  <p class="sport-meta">SPORT / WEEKLY LOG · 页面生成于 {generated_at}</p>

  <p>当前七日训练安排，以及按时间归档的训练复盘。</p>

  <nav class="sport-nav">
    <a href="#plan">本周计划</a>
    <a href="#history">历史复盘</a>
    <a href="/">返回首页</a>
  </nav>

  <section id="plan" class="sport-card">
    {plan_html}
  </section>

  <section id="history" class="sport-card">
    <h2>历史复盘</h2>
    {history_html}
  </section>
</div>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=Path("TRAINING_PLAN.md"))
    parser.add_argument("--history", type=Path, default=Path("history"))
    parser.add_argument("--output", type=Path, default=Path("dist/sport.md"))
    args = parser.parse_args()

    if not args.plan.is_file():
        raise SystemExit(f"Training plan not found: {args.plan}")
    if not args.history.is_dir():
        raise SystemExit(f"History directory not found: {args.history}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_page(args.plan, args.history), encoding="utf-8")
    print(f"Built {args.output}")


if __name__ == "__main__":
    main()
