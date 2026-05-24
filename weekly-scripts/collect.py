#!/usr/bin/env python3
"""
collect.py — 扫描过去 7 天的 ai-daily 日报文件，返回结构化摘要供 LLM 蒸馏。
用法: python3 collect.py [--date YYYY-MM-DD] [--days 7]
  --date: 结束日期（默认昨天）
  --days: 向前回溯天数（默认 7）
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

def get_vault() -> str:
    vault = os.environ.get("OBSIDIAN_VAULT", "/Users/admin/Documents/Obsidian Vault")
    return vault

def collect_daily_files(end_date: datetime, days: int) -> list[dict]:
    vault = get_vault()
    results_base = Path(vault) / "09_System/Automation/results"
    collected = []

    for i in range(days - 1, -1, -1):  # 从最早到最近
        day = end_date - timedelta(days=i)
        date_str = day.strftime("%Y-%m-%d")
        filepath = results_base / date_str / "06_ai_daily.md"

        entry = {
            "date": date_str,
            "weekday": ["周一","周二","周三","周四","周五","周六","周日"][day.weekday()],
            "found": False,
            "content": None,
        }

        if filepath.exists():
            text = filepath.read_text(encoding="utf-8")
            # 去掉 frontmatter
            if text.startswith("---"):
                parts = text.split("---", 2)
                text = parts[2].strip() if len(parts) >= 3 else text
            entry["found"] = True
            entry["content"] = text
        else:
            entry["content"] = f"[{date_str} 日报未生成]"

        collected.append(entry)

    return collected

def summarize(collected: list[dict]) -> dict:
    found = [e for e in collected if e["found"]]
    missing = [e["date"] for e in collected if not e["found"]]

    # 提取时间范围
    start = collected[0]["date"]
    end = collected[-1]["date"]
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    week_num = start_dt.isocalendar()[1]

    return {
        "week_range": f"{start} ~ {end}",
        "week_num": week_num,
        "total_days": len(collected),
        "found_days": len(found),
        "missing_dates": missing,
        "daily_entries": collected,
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="结束日期 YYYY-MM-DD（默认昨天）")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    if args.date:
        end_date = datetime.strptime(args.date, "%Y-%m-%d")
    else:
        end_date = datetime.today() - timedelta(days=1)

    collected = collect_daily_files(end_date, args.days)
    summary = summarize(collected)

    found_count = summary["found_days"]
    total = summary["total_days"]

    if found_count == 0:
        print(f"[ERROR] 0/{total} 天找到日报文件，无法生成周报", file=sys.stderr)
        sys.exit(1)

    if found_count < 4:
        print(f"[WARN] 只找到 {found_count}/{total} 天日报，内容可能不完整", file=sys.stderr)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        # 人类可读格式，直接喂给 LLM
        print(f"# 七日素材包 {summary['week_range']}（第{summary['week_num']}周）")
        print(f"找到 {found_count}/{total} 天，缺失：{summary['missing_dates'] or '无'}\n")
        print("=" * 60)
        for entry in summary["daily_entries"]:
            print(f"\n## {entry['date']} {entry['weekday']}")
            print(entry["content"] or "[无内容]")
        print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
