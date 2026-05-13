#!/usr/bin/env python3
"""
ai-daily 创作者素材更新器
Usage: python3 feed-update.py [--force] [--no-cdp] [--creator 歸藏]
Exit: 0=全部成功, 2=部分成功, 1=错误

输出: references/creator-feed/latest.md + references/creator-feed/YYYY-MM-DD.md
"""
import sys, re, json, time, argparse, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

SKILL_DIR   = Path(__file__).parent.parent
CONFIG_PATH = SKILL_DIR / "references" / "creator-config.json"
FEED_DIR    = SKILL_DIR / "references" / "creator-feed"
LATEST      = FEED_DIR / "latest.md"
CDP_BASE    = "http://localhost:3456"
TZ_CN       = timezone(timedelta(hours=8))

# ── HTTP helpers ──────────────────────────────────────────────────────
def http_get(url, extra_headers=None, timeout=12):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    if extra_headers:
        headers.update(extra_headers)
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            enc = r.headers.get_content_charset() or "utf-8"
            return r.read().decode(enc, errors="replace")
    except Exception:
        return None

# ── CDP helpers ───────────────────────────────────────────────────────
def cdp_check():
    return http_get(f"{CDP_BASE}/targets", timeout=3) is not None

def cdp_new(url):
    resp = http_get(f"{CDP_BASE}/new?url={urllib.parse.quote(url, safe='/:?=&#@')}")
    if resp:
        m = re.search(r'"targetId"\s*:\s*"([^"]+)"', resp)
        if m:
            return m.group(1)
    return None

def cdp_eval(tid, js):
    data = js.encode()
    req  = urllib.request.Request(
        f"{CDP_BASE}/eval?target={tid}", data=data, method="POST"
    )
    req.add_header("Content-Type", "text/plain")
    try:
        with urllib.request.urlopen(req, timeout=18) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception:
        return None

def cdp_close(tid):
    http_get(f"{CDP_BASE}/close?target={tid}")

def strip_tags(html):
    return re.sub(r"<[^>]+>", "", html or "").strip()

# ── WeChat via Sogou ──────────────────────────────────────────────────
def fetch_wechat(account_name, n=5, sogou_query=None):
    """Fetch recent WeChat articles via Sogou search (no login required)."""
    query = sogou_query or account_name
    q   = urllib.parse.quote(query)
    url = f"https://weixin.sogou.com/weixin?type=2&query={q}&ie=utf8"
    html = http_get(url)
    if not html:
        return []

    results = []

    # Strategy 1: txt-box divs (standard Sogou layout)
    blocks = re.findall(
        r'<div[^>]+class="[^"]*txt-box[^"]*"[^>]*>(.*?)</div>\s*(?:</li>|<p\s)',
        html, re.DOTALL
    )
    for block in blocks[:n]:
        title_m = re.search(r'<h3[^>]*>.*?<a[^>]*>(.*?)</a>', block, re.DOTALL)
        snip_m  = re.search(r'<p[^>]*class="[^"]*txt[^"]*"[^>]*>(.*?)</p>', block, re.DOTALL)
        date_m  = re.search(r'<span[^>]*class="[^"]*s3[^"]*"[^>]*>(.*?)</span>', block, re.DOTALL)
        title   = strip_tags(title_m.group(1)) if title_m else ""
        snippet = strip_tags(snip_m.group(1))[:200]  if snip_m  else ""
        date    = strip_tags(date_m.group(1))         if date_m  else ""
        if title:
            results.append({"title": title, "snippet": snippet, "date": date})

    # Strategy 2: fallback — grab h3 > a text directly
    if not results:
        raw_titles = re.findall(
            r'<h3[^>]*>.*?<a[^>]*>(.*?)</a>.*?</h3>', html, re.DOTALL
        )
        for t in raw_titles[:n]:
            clean = strip_tags(t)
            if clean and len(clean) > 4:
                results.append({"title": clean, "snippet": "", "date": ""})

    # Strategy 3: JSON-LD or structured data fallback
    if not results:
        json_blocks = re.findall(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', html, re.DOTALL)
        for jb in json_blocks:
            try:
                data = json.loads(jb)
                if isinstance(data, list):
                    for item in data[:n]:
                        if item.get("title"):
                            results.append({"title": item["title"], "snippet": item.get("abstract", "")[:200], "date": ""})
            except Exception:
                pass

    return results[:n]

# ── XHS via CDP ───────────────────────────────────────────────────────
def fetch_xhs(user_id, n=6):
    """Fetch recent XHS posts via CDP browser session."""
    url = f"https://www.xiaohongshu.com/user/profile/{user_id}"
    tid = cdp_new(url)
    if not tid:
        return []
    time.sleep(4)  # wait for page load + lazy images

    js = f"""
(function() {{
    var items = [];
    // Try multiple selector patterns (XHS changes class names frequently)
    var selectorSets = [
        ['[class*="note-item"]', '.title, .desc, [class*="title"]'],
        ['[data-e2e="user-note-item"]', '[data-e2e="note-title"], .title'],
        ['.feeds-page .section-box', '.cover-title, .desc'],
        ['.user-note-list-container .note-item', 'span'],
    ];
    for (var ss of selectorSets) {{
        var cards = document.querySelectorAll(ss[0]);
        if (cards.length === 0) continue;
        cards.forEach(function(card, i) {{
            if (i >= {n}) return;
            var titleEl = card.querySelector(ss[1]);
            var imgEl   = card.querySelector('img');
            var likeEl  = card.querySelector('[class*="like"] [class*="count"], [class*="count"]');
            items.push({{
                title:    titleEl ? titleEl.innerText.trim().slice(0, 80) : '',
                has_img:  imgEl ? true : false,
                likes:    likeEl ? likeEl.innerText.trim() : ''
            }});
        }});
        if (items.length > 0) break;
    }}
    // Last-resort: grab any visible text that looks like a post title
    if (items.length === 0) {{
        var spans = document.querySelectorAll('section span, .note-list span');
        var seen  = {{}};
        spans.forEach(function(s) {{
            var t = s.innerText.trim();
            if (t.length > 8 && t.length < 60 && !seen[t]) {{
                seen[t] = 1;
                items.push({{ title: t, has_img: false, likes: '' }});
            }}
        }});
    }}
    return JSON.stringify(items.slice(0, {n}));
}})()
"""
    raw = cdp_eval(tid, js)
    cdp_close(tid)

    if not raw:
        return []
    try:
        # CDP proxy wraps result: {"value": "<json string>"}
        outer = json.loads(raw.strip())
        value = outer.get("value", "[]")
        # value may be a list already or a JSON-encoded string
        if isinstance(value, list):
            data = value
        else:
            data = json.loads(str(value))
        return [d for d in data if d.get("title")][:n]
    except Exception:
        return []

# ── Pattern analysis ──────────────────────────────────────────────────
def detect_title_patterns(titles):
    patterns = []
    if any(re.search(r'\d', t) for t in titles):
        patterns.append("含数字/统计")
    if any("：" in t or ":" in t for t in titles):
        patterns.append("冒号隔事件+判断")
    if any(t.rstrip().endswith(("？", "?")) for t in titles):
        patterns.append("疑问句式")
    if any(len(re.sub(r'\s', '', t)) < 14 for t in titles):
        patterns.append("短标题风格(<14字)")
    if any(w in t for t in titles for w in ("但", "却", "反而", "没想到", "其实")):
        patterns.append("转折/反直觉")
    if any(w in t for t in titles for w in ("今天", "刚刚", "刚出", "最新")):
        patterns.append("强调今日性")
    return patterns or ["暂无明显规律"]

def visual_signal(items_xhs):
    if not items_xhs:
        return None
    img_count  = sum(1 for i in items_xhs if i.get("has_img"))
    total      = len(items_xhs)
    pct        = img_count / total if total else 0
    if pct >= 0.8:
        return "全部图文（配图率≥80%）"
    if pct >= 0.4:
        return "图文混合（配图率约40-80%）"
    return "多为纯文（配图率<40%）"

# ── Section builder ───────────────────────────────────────────────────
def build_section(creator, wx_items, xhs_items):
    now  = datetime.now(tz=TZ_CN).strftime("%Y-%m-%d %H:%M")
    name = creator["name"]
    lines = [f"### {name}", f"*{now}*  ·  {creator.get('focus', '')}", ""]

    # WeChat block
    if wx_items:
        lines.append("**公众号近期文章：**")
        for item in wx_items:
            lines.append(f"- {item['title']}")
            if item.get("snippet"):
                lines.append(f"  > {item['snippet'][:120]}")
            if item.get("date"):
                lines[-1] += f"  `{item['date']}`"
        wx_titles = [i["title"] for i in wx_items if i["title"]]
        if wx_titles:
            pats = detect_title_patterns(wx_titles)
            lines.append(f"\n*近期标题模式：{' · '.join(pats)}*")
        lines.append("")
    else:
        lines += [
            "**公众号：** 未获取到内容",
            "> Sogou 可能限流或账号名不匹配，可手动更新 `wechat_name` 字段",
            ""
        ]

    # XHS block
    if xhs_items:
        lines.append("**小红书近期笔记：**")
        for item in xhs_items:
            t = item.get("title", "")
            if t:
                likes = f"  （❤️ {item['likes']}）" if item.get("likes") else ""
                img   = " 🖼" if item.get("has_img") else ""
                lines.append(f"- {t}{img}{likes}")
        vis = visual_signal(xhs_items)
        if vis:
            lines.append(f"\n*配图模式：{vis}*")
        xhs_titles = [i.get("title", "") for i in xhs_items if i.get("title")]
        if xhs_titles:
            pats = detect_title_patterns(xhs_titles)
            lines.append(f"*小红书标题模式：{' · '.join(pats)}*")
        lines.append("")
    elif creator.get("xhs_user_id"):
        lines += ["**小红书：** CDP 未获取（页面结构可能变化，或未登录）", ""]
    else:
        lines += ["**小红书：** 未配置 `xhs_user_id`，参考 creator-config.json 填入", ""]

    return "\n".join(lines)

# ── Main ──────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force",   action="store_true", help="忽略24h缓存强制更新")
    ap.add_argument("--no-cdp",  action="store_true", help="不使用 CDP（跳过 XHS）")
    ap.add_argument("--creator", help="只更新指定创作者（按 name 字段）", default=None)
    args = ap.parse_args()

    if not CONFIG_PATH.exists():
        print(f"❌ 配置文件不存在: {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)

    config   = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    creators = config.get("creators", [])
    if args.creator:
        creators = [c for c in creators if c["name"] == args.creator]
        if not creators:
            print(f"❌ 未找到创作者: {args.creator}", file=sys.stderr)
            sys.exit(1)

    FEED_DIR.mkdir(parents=True, exist_ok=True)

    # Cache check (skip if <20h and not forced and not targeted)
    if LATEST.exists() and not args.force and not args.creator:
        age = (datetime.now().timestamp() - LATEST.stat().st_mtime) / 3600
        if age < 20:
            print(f"✅ 素材库已是最新（{age:.1f}h 前更新），跳过。--force 可强制更新。")
            sys.exit(0)

    use_cdp = not args.no_cdp and cdp_check()
    print(f"CDP: {'✅ 可用（将用于 XHS）' if use_cdp else '⚠️  不可用，XHS 跳过'}")
    if not use_cdp:
        print("  → 启动 CDP: 打开 Chrome → chrome://inspect → 开启 Allow remote debugging")

    sections, ok = [], 0

    for c in creators:
        name = c["name"]
        print(f"\n  [{name}] 抓取中...", end="", flush=True)

        wx_items  = fetch_wechat(
            c.get("wechat_name", name),
            sogou_query=c.get("sogou_query")
        )
        # Relevance filter: drop items that don't match any keyword
        kws = c.get("relevance_keywords", [])
        if kws:
            relevant = [
                item for item in wx_items
                if any(kw.lower() in (item["title"] + item.get("snippet","")).lower() for kw in kws)
            ]
            if relevant:  # only filter if we have some relevant results
                wx_items = relevant
        time.sleep(0.8)  # rate limit between requests

        xhs_items = []
        if use_cdp and c.get("xhs_user_id"):
            xhs_items = fetch_xhs(c["xhs_user_id"])

        print(f" 公众号 {len(wx_items)} 条, XHS {len(xhs_items)} 条")

        if wx_items or xhs_items:
            ok += 1

        sections.append(build_section(c, wx_items, xhs_items))

    date_str = datetime.now(tz=TZ_CN).strftime("%Y-%m-%d %H:%M")
    content = (
        f"# 创作者素材库 · {date_str}\n\n"
        "> 每次 ai-daily 运行前自动更新。用于 S2 风格校准——同频不模仿。\n"
        "> 手动更新：`python3 scripts/feed-update.py`\n"
        "> 强制更新：加 `--force` | 单人：加 `--creator 歸藏`\n\n"
        "---\n\n"
        + "\n\n---\n\n".join(sections)
    )

    # Write latest + dated backup
    LATEST.write_text(content, encoding="utf-8")
    dated = FEED_DIR / datetime.now(tz=TZ_CN).strftime("%Y-%m-%d.md")
    dated.write_text(content, encoding="utf-8")

    print(f"\n✅ 素材库已更新 ({ok}/{len(creators)} 创作者成功) → {LATEST}")

    if ok == 0:
        sys.exit(1)
    elif ok < len(creators):
        sys.exit(2)
    sys.exit(0)

if __name__ == "__main__":
    main()
