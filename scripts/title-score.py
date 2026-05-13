#!/usr/bin/env python3
"""
ai-daily 标题评分工具
Usage: python3 title-score.py "标题文字" [--platform wechat|xhs|x]
Output: JSON { score, breakdown, verdict, suggestions }
Exit 0 = PASS (≥6), 1 = FAIL (<6)

评分维度（各 0-2 分，满分 10）：
  情绪钩子  — 情绪词 / 意外结果 / 冲击感
  具体锚点  — 数字 / 时间 / 品牌名 / 金额
  读者利益  — 读者能得到/学到/注意什么（显性优于隐性）
  张力悬念  — 反差 / 疑问 / 悬念
  精准不废话 — 字数适中，每个词都在做功

平台最低通过线：公众号 ≥ 6，小红书 ≥ 7，X ≥ 6
"""
import sys
import re
import json
import argparse

# ── 情绪词库 ────────────────────────────────────────────────────────────
EMOTION_STRONG = [
    "无敌", "坏了", "震惊", "炸了", "终于", "拉警报", "出事了", "史上",
    "第一", "首例", "首个", "原来", "真相", "秘密", "居然", "竟然",
    "惊了", "疯了", "封神", "狠", "血赚", "血亏", "白白浪费", "在浪费",
    "都浪费", "全在浪费", "要命", "吓到", "看傻", "傻眼",
]
EMOTION_MILD = [
    "值得", "有意思", "不简单", "有点", "神了", "牛", "真的",
    "来了", "上线了", "发布了", "开放了", "开源了", "浪费了", "浪费",
    "没想到", "想不到", "有点狠", "有点猛",
]

# ── 具体锚点信号 ────────────────────────────────────────────────────────
NUMBER_PATTERN  = re.compile(r'\d+[\.\d]*\s*[%万亿元天分钟小时个条]|一[个条天分钟]|两[个条]|\d+[\.\d]*\s*分')
TIME_PATTERN    = re.compile(r'\d+\s*(?:分钟|小时|天|周|个月)|一[个]?下午|今天|今日|刚|刚刚')
BRAND_PATTERN   = re.compile(
    r'Claude|GPT|Anthropic|OpenAI|Google|Meta|Karpathy|Cursor|Codex|Gemini|Grok|'
    r'Mistral|DeepSeek|Kimi|MoMA|AWS|法院|Mira|苹果|微软|字节|百度|阿里',
    re.IGNORECASE
)

# ── 读者利益信号 ────────────────────────────────────────────────────────
READER_STRONG = [
    "你", "省", "赚", "少花", "不花", "白嫖", "免费", "教程", "方法",
    "攻略", "避坑", "怎么", "如何", "技巧", "用法", "上手", "入门",
]
READER_MILD = ["我", "用上", "学到", "值得", "必看", "该看", "注意"]

# ── 张力/悬念信号 ───────────────────────────────────────────────────────
TENSION_STRONG = ["？", "但", "却", "反而", "没想到", "出乎意料", "截然相反",
                  "同一天", "同天", "一边.*一边", "赔.*却", "被.*但"]
TENSION_MILD   = ["vs", "VS", "对比", "区别", "不同", "而不是"]

# ── 废话词 ──────────────────────────────────────────────────────────────
FILLER = ["值得注意的是", "不得不说", "随着", "深度", "全面", "解析",
          "总结", "大家", "让我们", "拭目以待", "AI正在改变"]

# ── 评分逻辑 ────────────────────────────────────────────────────────────
def score_emotion(title):
    for w in EMOTION_STRONG:
        if w in title:
            return 2, f"强情绪词「{w}」"
    for w in EMOTION_MILD:
        if w in title:
            return 1, f"弱情绪词「{w}」"
    return 0, "无情绪钩子"

def score_anchor(title):
    hits = []
    if NUMBER_PATTERN.search(title):  hits.append("数字")
    if TIME_PATTERN.search(title):    hits.append("时间")
    if BRAND_PATTERN.search(title):   hits.append("品牌/名词")
    if len(hits) >= 2: return 2, "+".join(hits)
    if len(hits) == 1: return 1, hits[0]
    return 0, "无具体锚点"

def score_reader(title):
    for w in READER_STRONG:
        if w in title:
            return 2, f"显性读者利益「{w}」"
    for w in READER_MILD:
        if w in title:
            return 1, f"隐含读者利益「{w}」"
    return 0, "无明显读者利益"

def score_tension(title):
    for p in TENSION_STRONG:
        if re.search(p, title):
            return 2, f"强张力「{p}」"
    for p in TENSION_MILD:
        if p.lower() in title.lower():
            return 1, f"弱张力「{p}」"
    return 0, "无反差/悬念"

def score_crisp(title):
    # CJK + ASCII words count
    cjk   = len(re.findall(r'[一-鿿]', title))
    words = len(re.findall(r'[a-zA-Z0-9]+', title))
    total = cjk + words
    filler_hit = [w for w in FILLER if w in title]
    if filler_hit:
        return 0, f"含废话词「{'、'.join(filler_hit)}」"
    if total <= 20 and total >= 8:
        return 2, f"字数精准（{total}字）"
    if total <= 25:
        return 1, f"字数适中（{total}字）"
    return 0, f"标题太长（{total}字）"

# ── 建议生成 ────────────────────────────────────────────────────────────
def generate_suggestions(breakdown):
    tips = []
    if breakdown["情绪钩子"][0] == 0:
        tips.append("加一个情绪词：「终于/坏了/原来/居然」——或改写成意外结果")
    if breakdown["具体锚点"][0] == 0:
        tips.append("加具体数字、时间或品牌名：「90%/三条/10万/今天」")
    if breakdown["读者利益"][0] == 0:
        tips.append("加读者视角：「你/省/怎么/教程」让读者知道为什么要点")
    if breakdown["张力悬念"][0] == 0:
        tips.append("加反差或疑问：「同一天/但/却/？」制造悬念")
    if breakdown["精准不废话"][0] == 0:
        tips.append("删掉废话词，压到 ≤20 字")
    return tips

# ── 主函数 ──────────────────────────────────────────────────────────────
def evaluate(title, platform="wechat"):
    threshold = {"wechat": 6, "xhs": 7, "x": 6}.get(platform, 6)

    dims = [
        ("情绪钩子",   score_emotion(title)),
        ("具体锚点",   score_anchor(title)),
        ("读者利益",   score_reader(title)),
        ("张力悬念",   score_tension(title)),
        ("精准不废话", score_crisp(title)),
    ]
    breakdown = {k: v for k, v in dims}
    total = sum(v[0] for v in breakdown.values())

    return {
        "title":     title,
        "platform":  platform,
        "score":     total,
        "max":       10,
        "threshold": threshold,
        "pass":      total >= threshold,
        "verdict":   "✅ PASS" if total >= threshold else "❌ FAIL",
        "breakdown": {k: {"score": v[0], "reason": v[1]} for k, v in dims},
        "suggestions": generate_suggestions(breakdown),
    }

def batch_evaluate(titles, platform="wechat"):
    results = [evaluate(t, platform) for t in titles]
    results.sort(key=lambda r: r["score"], reverse=True)
    return results

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("titles",    nargs="+", help="标题（可传多个进行对比）")
    ap.add_argument("--platform", default="wechat", choices=["wechat", "xhs", "x"])
    ap.add_argument("--json",    action="store_true", help="只输出 JSON")
    args = ap.parse_args()

    results = batch_evaluate(args.titles, args.platform)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        sys.exit(0 if results[0]["pass"] else 1)

    print(f"\n【标题评分 · {args.platform}平台 · 通过线 {results[0]['threshold']}/10】\n")
    for i, r in enumerate(results):
        rank = "🥇" if i == 0 else ("🥈" if i == 1 else "🥉")
        print(f"{rank} {r['score']}/10 {r['verdict']}  「{r['title']}」")
        for dim, v in r["breakdown"].items():
            bar = "●" * v["score"] + "○" * (2 - v["score"])
            print(f"   {bar} {dim}: {v['reason']}")
        if r["suggestions"]:
            print(f"   💡 改进: {r['suggestions'][0]}")
        print()

    best = results[0]
    if not best["pass"]:
        print("❌ 所有候选均未达标，建议重写")
        sys.exit(1)
    else:
        print(f"✅ 推荐使用: 「{best['title']}」（{best['score']}/10）")
        sys.exit(0)

if __name__ == "__main__":
    main()
