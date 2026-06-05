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
            f'<details class="history-item"{open_attribute}>'
            f"<summary>{html.escape(title)}</summary>"
            f'<div class="markdown-body">{body}</div>'
            "</details>"
        )

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    history_html = "\n".join(history_sections) or "<p>暂无历史复盘。</p>"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>训练计划与复盘</title>
  <style>
    :root {{ --bg:#f5f7f3; --card:#fff; --text:#1f2a24; --muted:#66736b; --line:#dce4dd; --accent:#287a52; --soft:#e8f3ec; }}
    @media (prefers-color-scheme: dark) {{ :root {{ --bg:#111714; --card:#19211d; --text:#edf3ef; --muted:#a7b4ac; --line:#34423a; --accent:#73d09d; --soft:#20382b; }} }}
    * {{ box-sizing:border-box; }} body {{ margin:0; background:var(--bg); color:var(--text); font:16px/1.75 system-ui,-apple-system,"Segoe UI",sans-serif; }}
    .shell {{ width:min(1080px, calc(100% - 32px)); margin:0 auto; padding:48px 0 72px; }}
    header {{ margin-bottom:28px; }} h1 {{ margin:0 0 8px; font-size:clamp(2rem,5vw,3.4rem); line-height:1.15; }}
    .subtitle,.updated {{ color:var(--muted); }} .updated {{ font-size:.88rem; }}
    nav {{ display:flex; gap:10px; margin:22px 0; }} nav a {{ color:var(--accent); background:var(--soft); padding:7px 13px; border-radius:999px; text-decoration:none; font-weight:650; }}
    .card {{ background:var(--card); border:1px solid var(--line); border-radius:18px; padding:clamp(20px,4vw,38px); margin:20px 0; box-shadow:0 12px 34px rgb(20 50 35 / 7%); }}
    h2 {{ margin-top:0; }} h3,h4,h5,h6 {{ margin-top:1.7em; line-height:1.3; }} a {{ color:var(--accent); }} li {{ margin:.35em 0; }}
    .table-wrap {{ overflow-x:auto; margin:18px 0; }} table {{ width:100%; border-collapse:collapse; min-width:760px; font-size:.94rem; }} th,td {{ border-bottom:1px solid var(--line); padding:11px 12px; text-align:left; vertical-align:top; }} th {{ background:var(--soft); }}
    code {{ background:var(--soft); border-radius:5px; padding:.1em .35em; }} details {{ border-top:1px solid var(--line); }} details:first-child {{ border-top:0; }}
    summary {{ cursor:pointer; padding:18px 0; color:var(--accent); font-weight:750; }} .history-item .markdown-body {{ padding:0 0 24px; }}
    footer {{ color:var(--muted); text-align:center; margin-top:34px; font-size:.9rem; }}
  </style>
</head>
<body>
  <main class="shell">
    <header>
      <p class="subtitle">SPORT / WEEKLY LOG</p>
      <h1>训练计划与复盘</h1>
      <p class="subtitle">当前七日训练安排，以及按时间归档的训练复盘。</p>
      <nav><a href="#plan">本周计划</a><a href="#history">历史复盘</a><a href="/">返回首页</a></nav>
      <p class="updated">页面生成于 {generated_at}</p>
    </header>
    <section id="plan" class="card markdown-body">{plan_html}</section>
    <section id="history" class="card"><h2>历史复盘</h2>{history_html}</section>
    <footer>由 Garmin 训练仓库每周自动更新</footer>
  </main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=Path("TRAINING_PLAN.md"))
    parser.add_argument("--history", type=Path, default=Path("history"))
    parser.add_argument("--output", type=Path, default=Path("dist/sport/index.html"))
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
