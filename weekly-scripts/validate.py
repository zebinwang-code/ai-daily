#!/usr/bin/env python3
"""
validate.py — 校验 AI七日谈 输出格式。
用法: python3 validate.py <output_file>
退出码: 0=通过, 1=失败
"""

import re
import sys
from pathlib import Path

REQUIRED_SECTIONS = [
    ("今周一句", r"今周一句"),
    ("七日速览", r"七日速览"),
    ("本周共性", r"本周共性"),
    ("周度洞察", r"周度洞察"),
]

RULES = {
    "min_chars": 200,
    "max_chars": 800,
    "min_daily_entries": 4,      # 七日速览至少 4 条
    "max_common_themes": 3,      # 共性最多 3 条
    "insight_min_chars": 60,     # 周度洞察最少 60 字
    "insight_max_chars": 200,    # 周度洞察最多 200 字
}

BANNED_PHRASES = [
    "值得注意的是", "在当下这个时代", "随着AI的发展",
    "不得不说", "毋庸置疑", "总的来说",
]

def check(filepath: str) -> tuple[bool, list[str]]:
    text = Path(filepath).read_text(encoding="utf-8")
    errors = []
    warnings = []

    # 1. 字数
    char_count = len(text.replace("\n", "").replace(" ", ""))
    if char_count < RULES["min_chars"]:
        errors.append(f"字数不足：{char_count} < {RULES['min_chars']}")
    if char_count > RULES["max_chars"]:
        warnings.append(f"字数偏多：{char_count} > {RULES['max_chars']}（周报应更精炼）")

    # 2. 必需段落
    for name, pattern in REQUIRED_SECTIONS:
        if not re.search(pattern, text):
            errors.append(f"缺少段落：{name}")

    # 3. 七日速览条目数
    daily_lines = [l for l in text.split("\n") if re.match(r"\d{2}/\d{2}", l.strip())]
    if len(daily_lines) < RULES["min_daily_entries"]:
        errors.append(f"七日速览条目不足：{len(daily_lines)} < {RULES['min_daily_entries']}")

    # 4. 本周共性条目数
    theme_lines = []
    in_themes = False
    for line in text.split("\n"):
        if "本周共性" in line:
            in_themes = True
            continue
        if in_themes and re.match(r"^(#{1,3}|---)", line):
            in_themes = False
        if in_themes and line.strip().startswith("▸"):
            theme_lines.append(line)
    if len(theme_lines) > RULES["max_common_themes"]:
        warnings.append(f"共性条目偏多：{len(theme_lines)}，建议压缩到 ≤{RULES['max_common_themes']}")

    # 5. 周度洞察字数
    insight_match = re.search(r"周度洞察\s*\n+(.+?)(?:\n---|\n#|\Z)", text, re.DOTALL)
    if insight_match:
        insight_text = insight_match.group(1).strip()
        insight_len = len(insight_text)
        if insight_len < RULES["insight_min_chars"]:
            errors.append(f"周度洞察太短：{insight_len} < {RULES['insight_min_chars']} 字")
        if insight_len > RULES["insight_max_chars"]:
            warnings.append(f"周度洞察偏长：{insight_len} > {RULES['insight_max_chars']} 字")

    # 6. 禁用词
    for phrase in BANNED_PHRASES:
        if phrase in text:
            warnings.append(f"含禁用词：「{phrase}」")

    return len(errors) == 0, errors + [f"[WARN] {w}" for w in warnings]

def main():
    if len(sys.argv) < 2:
        print("用法: python3 validate.py <output_file>")
        sys.exit(1)

    passed, messages = check(sys.argv[1])

    for msg in messages:
        print(msg)

    if passed:
        print("✓ 格式校验通过")
        sys.exit(0)
    else:
        print("✗ 格式校验失败")
        sys.exit(1)

if __name__ == "__main__":
    main()
