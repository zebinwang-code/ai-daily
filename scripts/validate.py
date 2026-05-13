#!/usr/bin/env python3
"""
ai-daily output validator
Usage: python3 validate.py <digest_file.md>
Exit 0 = PASS, 1 = FAIL
Prints JSON result to stdout.
"""
import sys
import re
import json
from pathlib import Path

# ── Schema ────────────────────────────────────────────────────────────
WECHAT_SCHEMA = {
    "max_chars": 600,       # hard limit; target is 500 (see SKILL.md)
    "required_sections": ["发生了什么", "灵感一闪", "工具推荐"],
    "story_marker": r"^‣",
    "story_min": 3,
    "story_max": 5,
}

XHS_SCHEMA = {
    "max_chars": 600,       # hard limit; target is 450 (see SKILL.md)
    "max_title_chars": 20,
}

X_SCHEMA = {
    "max_chars_per_tweet": 140,
    "tweet_separator": "---",
}

FORBIDDEN = [
    "值得注意的是", r"随着.{0,8}的发展", "让我们拭目以待",
    "不得不说", "颠覆性", "各有优劣", "深度解析", "综上所述",
    "AI正在改变世界", "值得期待$",
    r"不可忽视", r"毋庸置疑",
]

# 灵感一闪 quality signals
INSIGHT_FAIL = [
    r"^[灵感一闪\s]*AI 正在",
    r"^[灵感一闪\s]*这个时代",
    r"不像在.{0,10}，像在.{0,10}$",  # 线性推论结尾（太直）
]

# ── Helpers ───────────────────────────────────────────────────────────
def char_count(text):
    """Chinese-media 字数: CJK chars + each ASCII word counts as 1."""
    cjk = len(re.findall(r'[一-鿿㐀-䶿豈-﫿]', text))
    ascii_words = len(re.findall(r'[a-zA-Z0-9]+', text))
    return cjk + ascii_words

def extract_platform(content, header):
    """Extract text under a ## header until next ## or EOF."""
    pattern = rf'## {re.escape(header)}\s*\n(.*?)(?=\n## |\Z)'
    m = re.search(pattern, content, re.DOTALL)
    return m.group(1).strip() if m else ""

def check_forbidden(text, context=""):
    issues = []
    for pattern in FORBIDDEN:
        if re.search(pattern, text):
            issues.append(f"禁止词/句式 [{context}]: {pattern}")
    return issues

# ── Platform checks ───────────────────────────────────────────────────
def check_wechat(text):
    issues = []
    cc = char_count(text)
    if cc > WECHAT_SCHEMA["max_chars"]:
        issues.append(f"字数超限: {cc}/{WECHAT_SCHEMA['max_chars']}字")

    for sec in WECHAT_SCHEMA["required_sections"]:
        if sec not in text:
            issues.append(f"缺少 section: 「{sec}」")

    stories = re.findall(WECHAT_SCHEMA["story_marker"], text, re.MULTILINE)
    n = len(stories)
    if n < WECHAT_SCHEMA["story_min"]:
        issues.append(f"故事数量不足: {n} 条（最少 {WECHAT_SCHEMA['story_min']}）")
    elif n > WECHAT_SCHEMA["story_max"]:
        issues.append(f"故事数量超限: {n} 条（最多 {WECHAT_SCHEMA['story_max']}）")

    # 灵感一闪 quality check
    insight_m = re.search(r'灵感一闪\s*\n+(.*?)(?=\n---|\n工具|\Z)', text, re.DOTALL)
    if insight_m:
        insight = insight_m.group(1).strip()
        insight_cc = char_count(insight)
        if insight_cc < 60:
            issues.append(f"灵感一闪太短: {insight_cc}字（建议 60-100字）")
        if insight_cc > 150:
            issues.append(f"灵感一闪太长: {insight_cc}字（上限 150字）")
        for p in INSIGHT_FAIL:
            if re.search(p, insight):
                issues.append(f"灵感一闪疑似线性推论/格言: {p}")

    issues += check_forbidden(text, "公众号")
    return issues

def check_x(text):
    issues = []
    # Split tweets by standalone --- lines
    tweets = [t.strip() for t in re.split(r'\n---\n', text) if t.strip()]
    if not tweets:
        issues.append("X版: 未找到任何推文内容")
        return issues
    if len(tweets) > 3:
        issues.append(f"X版: 推文超过3条 ({len(tweets)} 条)")

    for i, tweet in enumerate(tweets, 1):
        cc = char_count(tweet)
        if cc > X_SCHEMA["max_chars_per_tweet"]:
            issues.append(f"X版 Tweet {i}: 超字数 {cc}/{X_SCHEMA['max_chars_per_tweet']}字")
        # Each tweet should be independently intelligible
        if len(tweet) < 20:
            issues.append(f"X版 Tweet {i}: 内容太短，可能解析错误")

    issues += check_forbidden(text, "X")
    return issues

def check_xhs(text):
    issues = []
    cc = char_count(text)
    if cc > XHS_SCHEMA["max_chars"]:
        issues.append(f"小红书字数超限: {cc}/{XHS_SCHEMA['max_chars']}字")

    title_m = re.search(r'^(?:标题[：:]?\s*)(.+)', text, re.MULTILINE)
    if not title_m:
        issues.append("小红书: 未找到标题行")
    else:
        title = title_m.group(1).strip().strip('「」【】')
        title_cc = char_count(title)
        if title_cc > XHS_SCHEMA["max_title_chars"]:
            issues.append(f"小红书标题超{XHS_SCHEMA['max_title_chars']}字: {title_cc}字「{title[:25]}」")

    issues += check_forbidden(text, "小红书")
    return issues

# ── Main ──────────────────────────────────────────────────────────────
def validate(path):
    content = Path(path).read_text(encoding='utf-8')

    wechat = extract_platform(content, "公众号版")
    x      = extract_platform(content, "X 版")
    xhs    = extract_platform(content, "小红书版")

    result = {
        "file": str(path),
        "platforms": {
            "wechat": {"found": bool(wechat), "issues": []},
            "x":      {"found": bool(x),      "issues": []},
            "xhs":    {"found": bool(xhs),    "issues": []},
        },
        "pass": True
    }

    if not wechat:
        result["platforms"]["wechat"]["issues"].append("未找到公众号版 section")
    else:
        result["platforms"]["wechat"]["issues"] = check_wechat(wechat)

    if not x:
        result["platforms"]["x"]["issues"].append("未找到 X 版 section")
    else:
        result["platforms"]["x"]["issues"] = check_x(x)

    if not xhs:
        result["platforms"]["xhs"]["issues"].append("未找到小红书版 section")
    else:
        result["platforms"]["xhs"]["issues"] = check_xhs(xhs)

    all_issues = (
        result["platforms"]["wechat"]["issues"] +
        result["platforms"]["x"]["issues"] +
        result["platforms"]["xhs"]["issues"]
    )
    result["pass"] = len(all_issues) == 0
    result["total_issues"] = len(all_issues)

    return result

def main():
    if len(sys.argv) < 2:
        print("Usage: validate.py <digest_file.md>", file=sys.stderr)
        sys.exit(2)

    result = validate(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["pass"]:
        print("\n✅ PASS — 格式校验通过", file=sys.stderr)
        sys.exit(0)
    else:
        print(f"\n❌ FAIL — {result['total_issues']} 个问题需修复", file=sys.stderr)
        for platform, data in result["platforms"].items():
            for issue in data["issues"]:
                print(f"  [{platform}] {issue}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
