#!/usr/bin/env python3
"""
ai-daily archive + knowledge base updater
Usage: python3 archive.py <digest_file.md> [--edited <final_file.md>]

After each successful run:
1. Appends a run record to references/knowledge-base.md
2. If --edited provided: records user edits as style signals
3. Every 7 runs: outputs a distillation prompt (does NOT auto-edit platform-voices.md)

Exit 0 = ok, 1 = error
"""
import sys
import re
import json
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
KB_PATH   = SKILL_DIR / "references" / "knowledge-base.md"

# ── Parsers ───────────────────────────────────────────────────────────
def extract_section(content, header):
    pattern = rf'## {re.escape(header)}\s*\n(.*?)(?=\n## |\Z)'
    m = re.search(pattern, content, re.DOTALL)
    return m.group(1).strip() if m else ""

def extract_stories(wechat_text):
    lines = re.findall(r'^‣\s*\*{0,2}(.+?)\*{0,2}[：:]', wechat_text, re.MULTILINE)
    return [l.strip() for l in lines]

def extract_tool(wechat_text):
    m = re.search(r'工具推荐\s*\n+\*{0,2}([^\n]+?)\*{0,2}[：:]', wechat_text)
    return m.group(1).strip() if m else "未解析"

def extract_insight_type(wechat_text):
    """Classify 灵感一闪 as: crossdomain / counterintuitive / comparison / linear"""
    m = re.search(r'灵感一闪\s*\n+(.*?)(?=\n---|\n工具|\Z)', wechat_text, re.DOTALL)
    if not m:
        return "unknown"
    insight = m.group(1).strip()
    # Rough heuristics
    cross_signals  = ["让我想到", "很像", "就像", "类比", "电话亭", "当年"]
    contra_signals = ["真正值得注意的", "反而", "恰恰相反", "但实际上"]
    compare_signals = ["截然相反", "同一天", "两家", "一边.*一边", "对比"]
    if any(s in insight for s in compare_signals):
        return "comparison"
    if any(s in insight for s in cross_signals):
        return "crossdomain"
    if any(s in insight for s in contra_signals):
        return "counterintuitive"
    return "linear"

def count_runs():
    if not KB_PATH.exists():
        return 0
    content = KB_PATH.read_text(encoding='utf-8')
    return len(re.findall(r'^### Run ', content, re.MULTILINE))

# ── Diff analysis ─────────────────────────────────────────────────────
def diff_summary(generated, edited):
    """Very lightweight diff: which sections changed significantly."""
    changes = []
    for section in ["发生了什么", "灵感一闪", "工具推荐"]:
        gen_s = extract_section(generated, section) if section in generated else ""
        edi_s = extract_section(edited,    section) if section in edited    else ""
        if gen_s != edi_s and len(gen_s) > 10:
            ratio = len(edi_s) / max(len(gen_s), 1)
            if ratio < 0.8 or ratio > 1.2:
                changes.append(f"{section} 大幅修改（长度比 {ratio:.1f}x）")
            else:
                changes.append(f"{section} 小幅修改")
    return changes if changes else ["无明显改动"]

# ── KB write ──────────────────────────────────────────────────────────
def append_run(date_str, stories, tool, insight_type, edit_signals, source_file):
    KB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not KB_PATH.exists():
        KB_PATH.write_text(
            "# AI Daily 知识库\n\n"
            "> 每次运行自动追加。每 7 次运行后输出蒸馏提示。\n\n"
            "---\n\n",
            encoding='utf-8'
        )

    entry = f"""### Run {date_str}

- **来源文件：** {source_file}
- **故事数量：** {len(stories)} 条
- **故事标题：**
{chr(10).join(f'  - {s}' for s in stories)}
- **工具推荐：** {tool}
- **灵感类型：** {insight_type}
- **用户修改信号：** {'; '.join(edit_signals)}

"""
    with open(KB_PATH, 'a', encoding='utf-8') as f:
        f.write(entry)

    return count_runs()

# ── Distillation prompt ───────────────────────────────────────────────
def distillation_prompt(n_runs):
    return f"""
━━━ 蒸馏提示 (第 {n_runs} 次运行，每 7 次触发一次) ━━━

请阅读 references/knowledge-base.md，对以下维度做一次蒸馏：

1. **灵感类型分布**：crossdomain / counterintuitive / comparison / linear 各几次？
   linear 占比如果 > 40%，在 platform-voices.md 灵感规则里加强跨域要求

2. **修改信号**：哪些 section 被用户反复修改？
   修改频繁的部分说明当前规则不够精确，需要更新 platform-voices.md 对应节

3. **工具推荐模式**：被接受的工具推荐有什么共同特征？
   被修改的有什么共同特征？更新 SKILL.md S2 工具推荐优先级

执行方式：把蒸馏结论直接更新到 references/platform-voices.md 和 SKILL.md，
不需要单独写报告。完成后在本 KB 追加一行：
`### Distill {n_runs} — YYYY-MM-DD — [改了什么]`
"""

# ── Main ──────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("digest",           help="生成的 digest 文件路径")
    ap.add_argument("--edited",         help="用户编辑后的最终文件（用于 diff）", default=None)
    ap.add_argument("--date",           help="日期 YYYY-MM-DD（默认今天）", default=None)
    ap.add_argument("--dry-run",        action="store_true", help="只打印，不写入 KB")
    args = ap.parse_args()

    date_str = args.date or datetime.now(tz=timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    content  = Path(args.digest).read_text(encoding='utf-8')
    wechat   = extract_section(content, "公众号版")

    stories      = extract_stories(wechat)
    tool         = extract_tool(wechat)
    insight_type = extract_insight_type(wechat)

    edit_signals = ["未提供编辑版本"]
    if args.edited:
        edited_content = Path(args.edited).read_text(encoding='utf-8')
        edit_signals   = diff_summary(wechat, extract_section(edited_content, "公众号版"))

    print(f"📅 {date_str}")
    print(f"📰 故事: {len(stories)} 条  |  工具: {tool}  |  灵感类型: {insight_type}")
    print(f"✏️  修改信号: {'; '.join(edit_signals)}")

    if args.dry_run:
        print("\n[dry-run] 未写入知识库")
        return

    n = append_run(date_str, stories, tool, insight_type, edit_signals, args.digest)
    print(f"\n✅ 已写入知识库（第 {n} 条运行记录）")

    if n > 0 and n % 7 == 0:
        print(distillation_prompt(n))

if __name__ == "__main__":
    main()
