---
name: ai-daily
description: >-
  AI 每日日报生成 Skill。主源：Daily Note（resource-morning 管道，OKR 分桶 RSS 精选）；
  辅源：aihot API（卡兹克聚合，补充遗漏条目）。蒸馏成「今日一句 + 发生了什么 + 灵感一闪 +
  工具推荐」四段式，同步输出公众号 / X / 小红书三版。风格干净轻快，500字以内。
  参考标杆：公众号→歸藏+宝玉xp；X→The Rundown AI；小红书→赛博禅心。
  触发：/ai-daily、AI日报、今天AI圈、每日AI、出日报、早报
---

# AI Daily — 每日 AI 日报

## 快速配置（换机必读）

首次使用前，在 shell 配置文件（`~/.zshrc` 或 `~/.bashrc`）中添加：

```bash
export OBSIDIAN_VAULT="/path/to/your/Obsidian Vault"   # 改成你的 Vault 根目录
```

然后 `source ~/.zshrc` 生效。  
Skill 读取的路径由 `$OBSIDIAN_VAULT` 驱动；不设则 fallback 到 `/Users/admin/Documents/Obsidian Vault`（原机默认值）。

| 变量 | 说明 | 示例 |
|------|------|------|
| `OBSIDIAN_VAULT` | Obsidian 库根目录 | `/Users/yourname/Documents/Obsidian Vault` |
| `CLAUDE_SKILL_DIR` | Skill 安装目录（Claude Code 自动注入，一般无需手动设置） | `~/.claude/skills/ai-daily` |

---

## 核心原则

1. **素材来自真实源头** — 主源是 Daily Note（resource-morning OKR 精选）；aihot 为辅助补充；禁止凭记忆构造新闻
2. **四段式是约束不是模板** — 今日一句/发生了什么/灵感一闪/工具推荐四段功能不可混淆
3. **平台适配是重写** — 公众号/X/小红书是三种不同阅读场景，不是改格式，是重新写
4. **今日性** — 每条信息必须能回答「为什么是今天」，避免任何时候都能发的通稿
5. **干净轻快** — 公众号版≤500字；X版每条≤140字；小红书版≤450字；无废话

---

## S0：创作者素材更新

每次生成前，先确保创作者素材库是最新的（24小时内自动跳过重复抓取）：

```bash
SKILL_DIR="${CLAUDE_SKILL_DIR:-$HOME/.claude/skills/ai-daily}"
python3 "$SKILL_DIR/scripts/feed-update.py"
```

成功后，读取素材信号用于 S2 风格校准：

```bash
cat "$SKILL_DIR/references/creator-feed/latest.md"
```

**S0 的作用：** 了解标杆创作者今天在写什么主题、用什么标题公式。不是模仿，是同频校准——如果他们集中写某个话题，你要差异化；如果他们出现新的标题模式（含数字/疑问句/转折式），可以参考。

**降级处理：** 抓取失败（exit 2）时继续使用 `references/platform-voices.md` 静态规则，不阻断主流程。

**XHS 首次配置：** 需在 `references/creator-config.json` 填入 `xhs_user_id`（从创作者小红书主页 URL 获取：`xiaohongshu.com/user/profile/{ID}`）。

**建议设置每日定时：** 每天早 7 点运行（`/schedule` skill 可配置），确保日报触发时素材已就绪。

---

## 调用接口（多 Agent 使用）

其他 Agent 调用此 skill 时支持以下参数，通过 SKILL.md 文本指令传递：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--date YYYY-MM-DD` | 指定日期（用于补跑历史日报） | 今天 |
| `--platforms wechat,x,xhs` | 只生成指定平台版本 | 全部三版 |
| `--dry-run` | 只生成内容，不写入文件、不归档 | false |
| `--output-json` | 以 JSON 格式返回三版内容（结构化调用） | false（返回 markdown） |
| `--edited <file>` | 用户编辑后的版本路径，用于 diff 分析 | 无 |

`--output-json` 返回结构：
```json
{
  "date": "YYYY-MM-DD",
  "wechat": "...",
  "x": "...",
  "xhs": "...",
  "validate_pass": true,
  "issues": []
}
```

---

## S1：素材收集

> **数据源优先级：** `03_Resources/_Morning/` Digest（resource-morning 管道）是主源，已聚合 aihot + 量子位 + waytoagi + Latent Space 等多源，带 hot_score 评分和角度分析；aihot API 仅作紧急 fallback（Digest 未生成时才独立调用）。

### Step 1.1 读取 Morning Digest（主源，必读）

resource-morning Master Agent 每天早上自动运行，产出 `03_Resources/_Morning/YYYY-MM/YYYY-MM-DD-Digest.md`，格式如下：
- **PART 1「AI 圈过去 24h」**：4-6 条大事，每条带 hot_score(1-10) + 来源列表 + 「对 AI 行业意味着什么」分析
- **PART 2「跟你有关·今天该做什么」**：OKR 标签行动项（今天最该做的 1 件事 + 顺手可做 3 件 + 仅需知道）
- **PART 3「精读推荐」**：2-3 篇深度文章，带导读和关联 KR
- 文件头 stats 显示：原始抓取量 / 聚合来源（aihot + 量子位 + waytoagi 等）/ 精选条数

```bash
DATE=$(date +%Y-%m-%d)
YM=$(date +%Y-%m)
VAULT="${OBSIDIAN_VAULT:-/Users/admin/Documents/Obsidian Vault}"
DIGEST="${VAULT}/03_Resources/_Morning/${YM}/${DATE}-Digest.md"
if [ -f "$DIGEST" ]; then
    # 读取 PART 1（AI 圈大事）+ PART 2 摘要即可，不需要全文
    python3 -c "
import re, sys
content = open('$DIGEST', encoding='utf-8').read()
# 提取 PART 1 和 PART 2（PART 3 精读推荐不需要）
m = re.search(r'(# 🌍 PART 1.*?)(?=# 📖 PART 3|\Z)', content, re.DOTALL)
if m:
    print(m.group(1)[:5000])
else:
    print(content[:5000])
"
else
    echo "⚠️  Morning Digest 未找到：$DIGEST"
    echo "   → 检查 resource-morning 是否正常运行，或手动确认路径"
    echo "   → 将使用 aihot fallback（见 Step 1.2）"
fi
```

**使用 Morning Digest 的好处：**
- 已去重聚合多源，无需再单独调 aihot
- hot_score 是天然的故事选题优先级信号（≥7 优先考虑）
- PART 2 的 OKR 标签帮助判断今日重点方向（如 KR3.2 = 小红书业务相关度高）
- 每条已有「意味着什么」角度，直接作为灵感一闪的触发点

### Step 1.2 aihot 补充（仅 Morning Digest 未生成时使用）

**触发条件：** `$DIGEST` 文件不存在，或文件存在但 PART 1 条目 < 3 条时才独立调用。

```bash
curl -sL \
  -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" \
  "https://aihot.virxact.com/api/public/daily" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
lead = data.get('lead', '')
sections = data.get('sections', [])
flashes = data.get('flashes', [])
print('Lead:', lead[:200] if lead else '(无)')
print()
for s in sections[:5]:
    print(f'## {s.get(\"title\",\"\")}')
    for item in s.get('items', [])[:3]:
        print(f'- {item.get(\"title\",\"\")}')
        if item.get('summary'):
            print(f'  {item[\"summary\"][:120]}')
print()
print('## Flashes')
for f in flashes[:5]:
    print(f'- {f.get(\"title\",\"\")}')
"
```

fallback（`/daily` 无数据时）：

```bash
since=$(date -u -v-24H '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u -d '24 hours ago' '+%Y-%m-%dT%H:%M:%SZ')
curl -sL \
  -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" \
  "https://aihot.virxact.com/api/public/items?mode=selected&since=${since}&take=20"
```

### Step 1.3 建候选池

整理所有素材，每条记录：标题/来源/分类（模型/产品/行业/工具/观点）/「今天为什么值得说」的一句判断。

---

## S2：蒸馏提炼

### 风格校准（写之前先看今天的创作者素材）

蒸馏开始前，从 S0 素材库里提取两个信号：

1. **今日话题覆盖**：标杆创作者今天在写哪些话题？你在写同类话题时要有差异化角度，而不是重复。
2. **近期标题模式**：他们用哪种标题公式在起效（含数字/疑问/转折/冒号式）？三版写作时可以参考这个节奏，但不要直接复制。

> 如果 creator-feed/latest.md 不存在或超过 48h，直接跳过，用 platform-voices.md 静态规则。

---

### 故事三问过滤（每条都必须过）

候选池里的每条新闻，都要回答这三个问题，有一个答不上来就淘汰：

1. **读者拿到这条信息，能做什么或思考什么？** — 纯财务数字（估值/融资/市值）如果没有落脚点（"这意味着什么"），直接淘汰；纯公告没有影响分析，淘汰
2. **为什么是今天，而不是任何一天都能发？** — 如果抽掉日期这条消息也能发，淘汰
3. **这是从业者或使用者视角有意义的信息，还是只是数字/报道？** — 行业围观新闻（「X 在 Y 地开会」）淘汰

从候选池最终选出：
- **故事 3-5 条**：今天最不能错过的事，覆盖至少 2 类（模型/产品/行业）
- **工具/技巧 1 个**：见下方优先级规则
- **洞察 1 个**：见下方灵感一闪规则

### 工具推荐优先级（从高到低）

1. **今天可以立刻试用的全新工具/功能**：用户之前完全不知道的东西，能立刻上手
2. **今天出现讨论热度的实用技巧**：shebang LLM 用法、结构化提示词框架、具体使用姿势——写出「怎么用」，不只是「它存在」
3. **有实质新 capability 的更新**：新功能本身能独立成一个使用场景，推时说清楚「具体怎么用」
4. **禁止**：「升级 Claude Code 就行」「下载 ChatGPT app」类推荐——升级不是工具推荐，除非展示了新功能的具体使用方法

### 灵感一闪规则（优先尝试跨域或反直觉）

**优先选用以下角度（越意外越好）：**
- **跨域联想**：今天的 AI 新闻让我想到另一个完全不同领域的什么历史或规律？「这和 XX 行业当年的 YY 很像」
- **反直觉视角**：今天大家都关注 X，但真正值得关注的其实是 Y，因为……
- **两条新闻放在一起看**：今天有没有两条看似无关的新闻，放在一起会碰出意外的火花？

**FAIL 示例（直接从新闻线性推出的）：**
> 「Anthropic 在搭脚手架，让大公司更容易用 AI」← 这只是对新闻的重复，不是洞察

**PASS 示例（有跳跃，有意外）：**
> 「中国移动今天上线 MoMA 接了 300 个模型，Anthropic 今天进 AWS。两家逻辑截然相反——一家说接越多模型平台越值钱，另一家说我的模型进越多云触达越多客户。电话亭消失那天没人在乎谁家电话亭最多。」← 有具体两条新闻、有对比、有跨域比喻、结尾留不确定性

---

## S3：三版并行输出

**三版同时生成，不分先后，全部完成后一次性展示。**

详细风格规则见 `references/platform-voices.md`。  
写前参考 `references/creator-feed/latest.md`：
- 公众号版 → 对照歸藏/宝玉 近期标题模式
- X 版 → 风格参考静态规则（无 X 创作者在 feed 中）
- 小红书版 → 对照赛博禅心 近期标题模式和配图信号

---

### 版本 A — 公众号

风格锚点：歸藏（有立场的快讯）+ 宝玉xp（技术含义简明解读）

**结构模板：**

```
标题：MM月DD日 AI圈 · [今日一句关键词]

[今日一句，25-30字，有立场，可以是质疑/惊叹/警觉/轻松]

---

发生了什么

‣ [事件1标题]：[一句话，≤40字，清楚说是什么+今天为什么值得说]
‣ [事件2标题]：[同上]
‣ [事件3标题]：[同上]
（可选第4/5条）

---

灵感一闪

[60-100字。从今天具体新闻触发的想法，有判断，落到具体，不升华，不套话]

---

工具推荐

[工具名]：[价值主张] · [适合谁] · [今天为什么推，必须有时效性理由，≤80字]
```

**格式规范：**
- 分节用 `---`（三条横线）
- 列表用 `‣` 前缀
- 禁止 emoji 装饰正文
- 禁止句式：「值得注意的是」「在当下这个时代」「随着…的发展」「不得不说」
- 公众号版总字数：200-500字

---

### 版本 B — X

风格锚点：Rowan Cheung / The Rundown AI（简洁 bullets + 一个 take）

**结构：1-3 条独立推文**

```
[Tweet 1] 
📅 MM/DD AI 圈 ·
▸ [故事1，≤35字]
▸ [故事2，≤35字]
▸ [故事3，≤35字]
[今日一句作为收尾，≤20字]

---

[Tweet 2，选做]
🔧 今日工具：[工具名]
[一句价值主张] + [今天为什么推]
≤120字

---

[Tweet 3，选做]
💡 [灵感一闪，独立 take，有观点]
≤100字
```

**格式规范：**
- 每条推文独立可传播，不依赖上下文
- **三个 Emoji 固定锁定：📅（Tweet1）、🔧（Tweet2）、💡（Tweet3）——不可替换**
- Emoji 只放行首，不重复出现
- 话题标签放最后：`#AI` `#AIDaily`（不超过 2 个）
- 每条字数：中文≤140字，英文≤280字符

---

### 版本 C — 小红书

风格锚点：赛博禅心（科技感 + 可读 + 高收藏率）

**结构模板：**

```
标题（≤20字，情绪/价值钩子）：
  例：「今天 AI 圈最炸的事来了」
  例：「5.DD AI 早知道 · 今天的主角是 XX」
  例：「发现一个神器，存下来用了 3 天」

---正文（300-450字）：

[开头 1-2 句钩子，直接挂上读者]

今天发生了什么 👇

① [事件1]
[1-2句说清，有判断]

② [事件2]
[1-2句说清，有判断]

③ [事件3]
[1-2句说清，有判断]

💡 今天的一个想法

[灵感一闪段落，50-80字，要有具体判断，像是在跟朋友说话]

🔧 今天的工具推荐

[工具名]：[价值主张，为什么今天推]
[适合的人：...]

[收尾 1 句，引导互动或收藏]

话题标签：#AI日报 #AI工具 #人工智能 + [当天相关话题1-2个]
```

**格式规范：**
- Emoji 作为段落标记（💡🔧①②③），不做装饰堆砌
- 分点不超过 3 句/条
- 收藏率 > 点赞率：内容要有「存下来以后用」的价值感
- 禁止：标题超 20 字、纯新闻聚合无观点、「建议大家」式说教

---

## S3.5：双重校验（必须通过才能存档）

三版写完后运行两层校验：

### 层 1：格式校验

```bash
SKILL_DIR="${CLAUDE_SKILL_DIR:-$HOME/.claude/skills/ai-daily}"
DATE=$(date +%Y-%m-%d)
VAULT="${OBSIDIAN_VAULT:-/Users/admin/Documents/Obsidian Vault}"
OUTPUT="${VAULT}/09_System/Automation/results/${DATE}/06_ai_daily.md"
python3 "$SKILL_DIR/scripts/validate.py" "$OUTPUT"
```

覆盖：字数、必填 section、故事数量（3-5条）、灵感一闪长度、禁止词、XHS 标题字数、X 推文字数。

### 层 2：标题评分校验

从写好的内容里提取标题，运行评分：

```bash
# 公众号标题（文件第一行或开头一句）
python3 "$SKILL_DIR/scripts/title-score.py" "公众号标题" --platform wechat

# 小红书标题（标题：后的内容）
python3 "$SKILL_DIR/scripts/title-score.py" "XHS标题" --platform xhs
```

**通过线：公众号 ≥ 7/10，小红书 ≥ 7/10**（格式校验通过线是 6，标题要求更高）

FAIL → 重新跑 S3.0 标题竞选，选更高分的候选，替换后重新校验。

---

## S4：存档 + 知识库归档

三版写入当日结果目录：

```bash
DATE=$(date +%Y-%m-%d)
VAULT="${OBSIDIAN_VAULT:-/Users/admin/Documents/Obsidian Vault}"
OUTPUT="${VAULT}/09_System/Automation/results/${DATE}/06_ai_daily.md"
```

文件格式：
```markdown
---
date: YYYY-MM-DD
generated_at: HH:MM
sources: aihot,morning_brief
---

# AI 日报 YYYY-MM-DD

## 公众号版
[内容]

---

## X 版
[内容]

---

## 小红书版
[内容]
```

存档后，追加运行记录到知识库：

```bash
SKILL_DIR="${CLAUDE_SKILL_DIR:-$HOME/.claude/skills/ai-daily}"
python3 "$SKILL_DIR/scripts/archive.py" "$OUTPUT"

# 如果用户提供了编辑后的版本（用于记录修改信号）：
# python3 "$SKILL_DIR/scripts/archive.py" "$OUTPUT" --edited "$EDITED_FILE"
```

archive.py 会：
- 解析故事数/工具名/灵感类型（crossdomain/counterintuitive/comparison/linear）
- 追加一条运行记录到 `references/knowledge-base.md`
- 每 7 次运行后输出蒸馏提示，指引更新 platform-voices.md

存档后直接展示三版给用户，并继续执行 S5（配图生成）→ S6（多平台发布）。

---

## S5：配图生成（ChatGPT CDP）

每次日报生成两张竖版图（9:16），存入当日结果目录：
- `img_daily.png` — 今日 AI 资讯信息图，结合当日内容
- `img_reflection.png` — 「日有所思」心得卡片，**内容需要暂停等用户输入**

### 流程

```bash
# 1. 打开 ChatGPT，进入图片生成模式
TARGET=$(curl -s "http://localhost:3456/new?url=https://chatgpt.com" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['targetId'])")
sleep 3

# 2. 点击「生成图片」入口按钮（UI 位于左侧边栏或工具栏）
curl -s -X POST "http://localhost:3456/eval?target=$TARGET" \
  -H "Content-Type: text/plain" \
  -d 'document.querySelector("[data-testid=\"gizmo-selector-button-dalle\"]")?.click() || document.querySelector("button[aria-label*=\"图\"]")?.click()'
sleep 2
```

**Image 1 — 资讯信息图**

提示词模板（将 `{{TITLE}}` `{{EVENTS}}` 替换为当日实际内容）：

```
modern flat infographic, minimalist, vertical poster 9:16, soft pastel gradient background
(blue-purple-peach), tech newsletter style, futuristic, abstract icons and circular motifs,
floating shapes, semi-transparent layers, smooth gradients, clean hierarchical layout,
bold Chinese headline, light shadows and highlights, thematic symbols placeholder.
Include text: main title「AI 圈 · MM月DD日」, subtitle「{{TITLE}}」,
3 content cards: {{EVENT1}} / {{EVENT2}} / {{EVENT3}}
```

```bash
# 3. 找到图片模式 composer 并输入提示词
PROMPT_B64=$(echo -n "$PROMPT" | base64)
curl -s -X POST "http://localhost:3456/eval?target=$TARGET" \
  -H "Content-Type: text/plain" \
  -d "
var __b64d=function(s){var b=atob(s),ar=new Uint8Array(b.length);for(var i=0;i<b.length;i++)ar[i]=b.charCodeAt(i);return new TextDecoder('utf-8').decode(ar);};
var box=document.querySelector('p[data-placeholder=\"描述或编辑图片\"]') || document.querySelector('[contenteditable=\"true\"]');
box.focus();
document.execCommand('insertText',false,__b64d('$PROMPT_B64'));
'done'
"
sleep 1
curl -s -X POST "http://localhost:3456/click?target=$TARGET" -d '.composer-submit-btn'
# 等待生成（约 30s）
sleep 35
```

**Image 2 — 「日有所思」心得卡**

⚠️ **此步骤必须暂停，等用户提供当日心得文字**：

> 「请输入今日心得（日有所思）——1-3句话，放进卡片里。」

收到用户输入后，用以下提示词生成：

```
A minimalist vertical card 9:16, calm and philosophical aesthetic.
Soft warm gradient background (cream-ivory to light sage green).
Handwritten-style Chinese text centered: 「日有所思」as the main title (bold, large),
below it smaller text: 「{{USER_TEXT_FIRST_LINE}}」
bottom area: full reflection text in smaller font: 「{{USER_FULL_TEXT}}」
Clean white space, no decorative elements, elegant serif-like Chinese typography,
subtle paper texture, muted warm tones.
```

### 下载保存

图片生成完成后，用 CDP fetch + base64 解码保存（需在浏览器已登录 ChatGPT 的 tab 中执行，URL 含 `estuary` 字样）：

```python
import subprocess, json, base64

def download_chatgpt_image(target_id, out_path):
    # 1. 获取图片 URL
    r = subprocess.run(
        ['curl','-s','-X','POST',f'http://localhost:3456/eval?target={target_id}',
         '-H','Content-Type: text/plain',
         '-d','JSON.stringify(Array.from(document.querySelectorAll("img[src*=estuary]")).map(i=>i.src)[0])'],
        capture_output=True, text=True)
    img_url = json.loads(r.stdout)['value'].strip('"')

    # 2. 在浏览器内 fetch（带 cookie），分块读取 base64
    fetch_js = f'fetch("{img_url}").then(r=>r.arrayBuffer()).then(buf=>{{var a=new Uint8Array(buf),b="",c=8192;for(var i=0;i<a.length;i+=c)b+=String.fromCharCode.apply(null,a.subarray(i,i+c));window.__imgb64=btoa(b);return window.__imgb64.length;}})'
    subprocess.run(['curl','-s','-X','POST',f'http://localhost:3456/eval?target={target_id}',
                    '-H','Content-Type: text/plain','-d',fetch_js], capture_output=True)

    # 3. 分块取出 base64 并解码
    total = json.loads(subprocess.run(
        ['curl','-s','-X','POST',f'http://localhost:3456/eval?target={target_id}',
         '-H','Content-Type: text/plain','-d','window.__imgb64.length'],
        capture_output=True,text=True).stdout)['value']
    chunks, size = [], 500000
    for start in range(0, total, size):
        r = subprocess.run(
            ['curl','-s','-X','POST',f'http://localhost:3456/eval?target={target_id}',
             '-H','Content-Type: text/plain','-d',f'window.__imgb64.substring({start},{start+size})'],
            capture_output=True, text=True)
        chunks.append(json.loads(r.stdout)['value'])
    with open(out_path, 'wb') as f:
        f.write(base64.b64decode(''.join(chunks)))
    print(f"Saved {out_path} ({total} b64 chars)")
```

---

## S6：多平台发布

三版内容 + 两张图就绪后，依次发布。公众号走 content-harness；X / 小红书用 CDP。

### S6.1 公众号发布

调用 content-harness skill（已有完整 CDP 流程，含 filetransfer 上传封面 + operate_appmsg API 写正文）：

```
/content-harness --platform wechat --content $OUTPUT --cover img_daily.png
```

关键经验（详见 `web-access/references/site-patterns/mp.weixin.qq.com.md`）：
- base64 解码函数命名用 `__b64d`，不能用 `dec`（WeChat 保留变量）
- curl 发 JS 时加 `-H "Content-Type: text/plain"` 保留 `+` 字符
- 注入正文后需再单独 eval 一次设置标题（Vue 会把第一段文字同步到 title 框）

### S6.2 X（Twitter）发布

```bash
# 1. 打开 compose 窗口
TARGET_X=$(curl -s "http://localhost:3456/new?url=https://x.com/compose/post" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['targetId'])")
sleep 3

# 2. 注入 Tweet 1（通过 execCommand insertText，不用 value setter）
TWEET1_B64=$(echo -n "$TWEET1" | base64)
curl -s -X POST "http://localhost:3456/eval?target=$TARGET_X" \
  -H "Content-Type: text/plain" \
  -d "
var __b64d=function(s){var b=atob(s),ar=new Uint8Array(b.length);for(var i=0;i<b.length;i++)ar[i]=b.charCodeAt(i);return new TextDecoder('utf-8').decode(ar);};
var box=document.querySelector('[data-testid=\"tweetTextarea_0\"]');
box.focus(); document.execCommand('insertText',false,__b64d('$TWEET1_B64')); 'done'
"

# 3. 注入 Tweet 2（第二个 tweetTextarea_0 实例 = 线程续帖框）
TWEET2_B64=$(echo -n "$TWEET2" | base64)
curl -s -X POST "http://localhost:3456/eval?target=$TARGET_X" \
  -H "Content-Type: text/plain" \
  -d "
var __b64d=function(s){var b=atob(s),ar=new Uint8Array(b.length);for(var i=0;i<b.length;i++)ar[i]=b.charCodeAt(i);return new TextDecoder('utf-8').decode(ar);};
var boxes=document.querySelectorAll('[data-testid=\"tweetTextarea_0\"]');
var box=boxes[boxes.length-1]; box.focus();
document.execCommand('insertText',false,__b64d('$TWEET2_B64')); 'done'
"
sleep 1

# 4. 点 addButton 添加 Tweet 3 槽位
curl -s -X POST "http://localhost:3456/click?target=$TARGET_X" -d '[data-testid="addButton"]'
sleep 1

# 5. 注入 Tweet 3（同上，取最后一个 textarea）
TWEET3_B64=$(echo -n "$TWEET3" | base64)
curl -s -X POST "http://localhost:3456/eval?target=$TARGET_X" \
  -H "Content-Type: text/plain" \
  -d "
var __b64d=function(s){var b=atob(s),ar=new Uint8Array(b.length);for(var i=0;i<b.length;i++)ar[i]=b.charCodeAt(i);return new TextDecoder('utf-8').decode(ar);};
var boxes=document.querySelectorAll('[data-testid=\"tweetTextarea_0\"]');
boxes[boxes.length-1].focus();
document.execCommand('insertText',false,__b64d('$TWEET3_B64')); 'done'
"

# 6. 发布
curl -s -X POST "http://localhost:3456/click?target=$TARGET_X" -d '[data-testid="tweetButton"]'
sleep 3
curl -s "http://localhost:3456/close?target=$TARGET_X"
```

**已知陷阱（2026-05-13 验证）：**
- X 的 hashtag 自动补全下拉框不影响提交，直接点 Post 即可
- 线程续帖框与 tweet1 框同名（均为 `tweetTextarea_0`），用 `querySelectorAll(...)[last]` 取最后一个
- 账号若处于只读模式（刚注册/被限制）会报 "Your account may not be allowed to perform this action"，需人工处理
- 不支持在 compose 弹窗内直接上传图片到线程（图片发布建议人工操作）

### S6.3 小红书发布

```bash
# 1. 打开创作者中心
TARGET_XHS=$(curl -s "http://localhost:3456/new?url=https://creator.xiaohongshu.com/publish/publish" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['targetId'])")
sleep 4

# 2. 点击「上传图片」，选择封面图
curl -s -X POST "http://localhost:3456/setFiles?target=$TARGET_XHS" \
  -H "Content-Type: application/json" \
  -d "{\"selector\":\"input[type=file]\",\"files\":[\"$IMG_DAILY_PATH\"]}"
sleep 3

# 3. 注入标题
TITLE_B64=$(echo -n "$XHS_TITLE" | base64)
curl -s -X POST "http://localhost:3456/eval?target=$TARGET_XHS" \
  -H "Content-Type: text/plain" \
  -d "
var __b64d=function(s){var b=atob(s),ar=new Uint8Array(b.length);for(var i=0;i<b.length;i++)ar[i]=b.charCodeAt(i);return new TextDecoder('utf-8').decode(ar);};
var titleBox=document.querySelector('.titleInput') || document.querySelector('input[placeholder*=\"标题\"]');
var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
s.call(titleBox,__b64d('$TITLE_B64'));
titleBox.dispatchEvent(new Event('input',{bubbles:true}));
'done'
"

# 4. 注入正文
BODY_B64=$(echo -n "$XHS_BODY" | base64)
curl -s -X POST "http://localhost:3456/eval?target=$TARGET_XHS" \
  -H "Content-Type: text/plain" \
  -d "
var __b64d=function(s){var b=atob(s),ar=new Uint8Array(b.length);for(var i=0;i<b.length;i++)ar[i]=b.charCodeAt(i);return new TextDecoder('utf-8').decode(ar);};
var ed=document.querySelector('.ql-editor') || document.querySelector('[contenteditable=true]');
ed.focus();
document.execCommand('insertText',false,__b64d('$BODY_B64'));
'done'
"

# 5. 添加话题标签（点击「#话题」按钮后 eval 注入）
# 建议手动添加以避免话题搜索触发反爬

# 6. 发布
curl -s -X POST "http://localhost:3456/click?target=$TARGET_XHS" -d '.publishBtn'
sleep 3
curl -s "http://localhost:3456/close?target=$TARGET_XHS"
```

**已知陷阱（2026-05-13 经验）：**
- 创作者中心需已登录状态（用户日常 Chrome 天然携带）
- 图片上传后有处理时间（约 2-3s），需 sleep 后再填文字
- XHS 编辑器可能是 Quill（`.ql-editor`）或自定义 contenteditable，截图确认后选择
- 话题标签（#AI日报等）自动补全会触发网络请求，建议最后手动点选
- 封面图建议用 img_daily.png（信息图），比文字截图更吸引点击

---

## 展示格式

三版一次性输出，用 `---` 分隔，标注版本名。不暂停，不等确认，全出完再交给用户。

---

## 禁止事项

| 禁止 | 说明 |
|------|------|
| 凭记忆构造新闻 | 所有「发生了什么」必须有 aihot 或晨报来源支撑 |
| 万年常青工具推荐 | 工具推荐必须有今日时效性触发 |
| 格言式灵感一闪 | 「AI 正在改变世界」类直接重写 |
| 模糊的今日一句 | 「今天很热闹」是 FAIL，有具体主语和判断才是 PASS |
| 三版只改格式 | 三版是三种语境，要重新组织语言，不是同一稿改缩进 |
