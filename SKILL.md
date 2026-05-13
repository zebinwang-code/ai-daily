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
- Emoji 最多 1 个/推文，只放开头功能性位置
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

存档后直接展示三版给用户。发布：公众号版走 content-harness 发布流程；X/小红书版手动复制。

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
