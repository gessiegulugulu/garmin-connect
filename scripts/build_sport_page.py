#!/usr/bin/env python3
"""Build a standalone sport dashboard from the training plan and history.

The output is a Hugo-compatible Markdown page with front matter, embedded CSS,
and rendered HTML converted from a small Markdown subset.
"""

from __future__ import annotations

import argparse
import html
import re
from datetime import datetime, timezone
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


def history_title_from_path(path: Path) -> str:
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", path.stem)
    if date_match:
        return f"{date_match.group(1)} 周复盘"
    return path.stem.replace("-", " ")


def build_page(plan_path: Path, history_dir: Path) -> str:
    history_files = sorted(history_dir.rglob("*.md"), reverse=True)
    plan_html = render_markdown(plan_path.read_text(encoding="utf-8"))
    history_sections: list[str] = []

    for path in history_files:
        title = history_title_from_path(path)
        body = render_markdown(path.read_text(encoding="utf-8"))
        history_sections.append(
            '<details class="sport-history-item">'
            f"<summary>{html.escape(title)}</summary>"
            f'<div class="sport-markdown-body">{body}</div>'
            "</details>"
        )

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    history_html = "\n".join(history_sections) or '<p class="sport-empty">暂无历史复盘。</p>'

    return f"""---
title: 训练计划与复盘
url: /sport/
summary: Garmin 训练计划与每周复盘
---

<style>
  .sport-dashboard {{
    margin-top: 1.5rem;
    line-height: 1.75;
  }}

  .sport-dashboard .sport-hero {{
    position: relative;
    overflow: hidden;
    border: 1px solid var(--border);
    border-radius: calc(var(--radius) + 8px);
    padding: 1.7rem 1.3rem;
    margin-bottom: 1.5rem;
    text-align: center;
    background:
      radial-gradient(circle at top left, rgba(120, 160, 255, 0.16), transparent 32rem),
      radial-gradient(circle at bottom right, rgba(90, 180, 140, 0.12), transparent 28rem),
      var(--entry);
  }}

  .sport-dashboard .sport-meta {{
    color: var(--secondary);
    font-size: 0.86rem;
    margin: 0 0 0.45rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }}

  .sport-dashboard .sport-title {{
    margin: 0;
    font-size: clamp(1.6rem, 4vw, 2.35rem);
    line-height: 1.25;
  }}

  .sport-dashboard .sport-subtitle {{
    margin: 0.75rem auto 0;
    max-width: 42rem;
    color: var(--secondary);
  }}

  .sport-dashboard .sport-nav {{
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 0.7rem;
    margin: 1.5rem auto 2.2rem;
  }}

  .sport-dashboard .sport-nav a {{
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 0.42rem 1rem;
    text-decoration: none;
    font-size: 0.92rem;
    background: var(--entry);
    transition: transform 0.15s ease, border-color 0.15s ease, background 0.15s ease;
  }}

  .sport-dashboard .sport-nav a:hover {{
    transform: translateY(-1px);
    border-color: var(--primary);
    background: var(--code-bg);
  }}

  .sport-dashboard .sport-card {{
    border: 1px solid var(--border);
    border-radius: calc(var(--radius) + 4px);
    padding: 1.35rem;
    margin: 1.35rem 0;
    background: var(--entry);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.04);
  }}

  .sport-dashboard h2,
  .sport-dashboard h3,
  .sport-dashboard h4,
  .sport-dashboard h5,
  .sport-dashboard h6 {{
    margin-top: 1.5em;
    margin-bottom: 0.65em;
  }}

  .sport-dashboard #plan > h2:first-child,
  .sport-dashboard #history > h2:first-child {{
    margin-top: 0;
  }}

  .sport-dashboard .table-wrap {{
    overflow-x: auto;
    margin: 1rem 0;
    border: 1px solid var(--border);
    border-radius: var(--radius);
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
    padding: 0.7rem 0.8rem;
    text-align: left;
    vertical-align: top;
  }}

  .sport-dashboard tr:last-child td {{
    border-bottom: 0;
  }}

  .sport-dashboard th {{
    background: var(--code-bg);
    font-weight: 700;
    white-space: nowrap;
  }}

  .sport-dashboard code {{
    background: var(--code-bg);
    border-radius: 5px;
    padding: 0.12em 0.38em;
    font-size: 0.92em;
  }}

  .sport-dashboard ul {{
    padding-left: 1.35rem;
  }}

  .sport-dashboard li + li {{
    margin-top: 0.25rem;
  }}

  .sport-dashboard hr {{
    border: 0;
    border-top: 1px solid var(--border);
    margin: 1.25rem 0;
  }}

  .sport-dashboard .sport-history-list {{
    position: relative;
    margin-top: 0.2rem;
  }}

  .sport-dashboard .sport-history-item {{
    position: relative;
    border: 0;
    margin-left: 0.85rem;
    padding-left: 1.6rem;
  }}

  .sport-dashboard .sport-history-item::before {{
    content: "";
    position: absolute;
    left: 0;
    top: 0.2rem;
    bottom: -0.2rem;
    width: 2px;
    background: var(--border);
  }}

  .sport-dashboard .sport-history-item:last-child::before {{
    bottom: 1.2rem;
  }}

  .sport-dashboard .sport-history-item summary {{
    position: relative;
    cursor: pointer;
    list-style: none;
    padding: 0.9rem 0 0.9rem 0.2rem;
    font-weight: 700;
    color: var(--primary);
    outline: none;
  }}

  .sport-dashboard .sport-history-item summary::-webkit-details-marker {{
    display: none;
  }}

  .sport-dashboard .sport-history-item summary::before {{
    content: "";
    position: absolute;
    left: -1.72rem;
    top: 1.35rem;
    width: 0.72rem;
    height: 0.72rem;
    border-radius: 999px;
    background: var(--entry);
    border: 2px solid var(--primary);
    box-shadow: 0 0 0 4px var(--theme);
  }}

  .sport-dashboard .sport-history-item summary::after {{
    content: "展开";
    display: inline-block;
    margin-left: 0.65rem;
    color: var(--secondary);
    font-size: 0.78rem;
    font-weight: 500;
    line-height: 1.4;
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 0.12rem 0.48rem;
    vertical-align: middle;
  }}

  .sport-dashboard .sport-history-item[open] summary::after {{
    content: "收起";
  }}

  .sport-dashboard .sport-history-item[open] summary::before {{
    background: var(--primary);
  }}

  .sport-dashboard .sport-markdown-body {{
    margin: 0.1rem 0 1.2rem;
    padding: 1rem 1.1rem;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--theme);
  }}

  .sport-dashboard .sport-markdown-body > *:first-child {{
    margin-top: 0;
  }}

  .sport-dashboard .sport-markdown-body > *:last-child {{
    margin-bottom: 0;
  }}

  .sport-dashboard .sport-empty {{
    margin: 0;
    color: var(--secondary);
  }}

  @media (max-width: 720px) {{
    .sport-dashboard .sport-hero {{
      padding: 1.3rem 1rem;
    }}

    .sport-dashboard .sport-card {{
      padding: 1rem;
    }}

    .sport-dashboard .sport-history-item {{
      margin-left: 0.5rem;
      padding-left: 1.25rem;
    }}

    .sport-dashboard .sport-history-item summary::before {{
      left: -1.37rem;
    }}

    .sport-dashboard .sport-markdown-body {{
      padding: 0.9rem;
    }}
  }}
</style>

<div class="sport-dashboard">
  <header class="sport-hero">
    <p class="sport-meta">SPORT / WEEKLY LOG · 页面生成于 {generated_at}</p>
    <h1 class="sport-title">训练计划与复盘</h1>
    <p class="sport-subtitle">当前七日训练安排，以及按时间归档的训练复盘。</p>
  </header>

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
    <div class="sport-history-list">
      {history_html}
    </div>
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