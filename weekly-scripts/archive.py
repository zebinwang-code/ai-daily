#!/usr/bin/env python3
"""
archive.py — 将生成的 AI七日谈 存入 weekly 归档目录，并维护周索引。
用法: python3 archive.py <content_file> --week YYYY-WXX --range "MM/DD-MM/DD"
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

def get_vault() -> str:
    return os.environ.get("OBSIDIAN_VAULT", "/Users/admin/Documents/Obsidian Vault")

def get_output_dir() -> Path:
    vault = get_vault()
    out = Path(vault) / "09_System/Automation/results/weekly"
    out.mkdir(parents=True, exist_ok=True)
    return out

def archive(content: str, week_id: str, date_range: str) -> Path:
    out_dir = get_output_dir()
    filename = f"{week_id}-ai-weekly.md"
    filepath = out_dir / filename

    # 添加 frontmatter
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    frontmatter = f"""---
week: {week_id}
range: {date_range}
generated_at: {now}
skill: ai-weekly
---

"""
    filepath.write_text(frontmatter + content, encoding="utf-8")
    print(f"✓ 存档：{filepath}")

    # 更新周索引
    update_index(out_dir, week_id, date_range, filepath.name)

    return filepath

def update_index(out_dir: Path, week_id: str, date_range: str, filename: str):
    index_path = out_dir / "index.md"

    # 读取现有索引
    existing = ""
    if index_path.exists():
        existing = index_path.read_text(encoding="utf-8")

    # 如果本周条目已存在就更新，否则追加
    new_entry = f"| {week_id} | {date_range} | [{filename}]({filename}) |"

    if week_id in existing:
        lines = existing.split("\n")
        lines = [new_entry if week_id in l else l for l in lines]
        updated = "\n".join(lines)
    else:
        if not existing:
            existing = "# AI七日谈 周报索引\n\n| 周次 | 日期范围 | 文件 |\n|------|---------|------|\n"
        updated = existing.rstrip() + "\n" + new_entry + "\n"

    index_path.write_text(updated, encoding="utf-8")
    print(f"✓ 索引更新：{index_path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("content_file", help="待存档的内容文件路径")
    parser.add_argument("--week", required=True, help="周次 ID，如 2026-W21")
    parser.add_argument("--range", dest="date_range", required=True, help="日期范围，如 05/12-05/18")
    args = parser.parse_args()

    content_path = Path(args.content_file)
    if not content_path.exists():
        print(f"[ERROR] 文件不存在：{content_path}", file=sys.stderr)
        sys.exit(1)

    content = content_path.read_text(encoding="utf-8")
    # 去掉 frontmatter（如有）
    if content.startswith("---"):
        parts = content.split("---", 2)
        content = parts[2].strip() if len(parts) >= 3 else content

    archived_path = archive(content, args.week, args.date_range)
    print(f"路径：{archived_path}")

if __name__ == "__main__":
    main()
