# AI七日谈 — 周度 AI 观察

> 把7天的日报压缩成一份有时间纵深的观察。不是汇总，是提炼——找出只有看完整周才能看见的东西。

## 触发

`/ai-weekly` — 对过去 7 天做周度蒸馏，默认回溯至昨天。

参数：
- `--date YYYY-MM-DD`：指定结束日期（默认昨天）
- `--days N`：回溯天数（默认 7，最多 14）

---

## 核心原则

1. **周报 ≠ 日报 × 7** — 不汇总新闻条目，只提炼跨天信号；每个故事最多出现一次，以「它这周在演变」的视角出现
2. **共性优先** — 本周什么词/趋势/品牌反复出现？3次以上才算共性，1次偶发不写
3. **时间维度洞察** — 周度洞察只写"如果只看一天看不到、但看完7天能看到的东西"；不写每天都能写的通稿
4. **普通人视角** — 延续 ai-daily 的选材标准；共性提炼也要落脚到"这对用普通人意味着什么"
5. **极简输出** — 全文 ≤ 600 字；七日速览每条 ≤ 25 字；周度洞察 60-150 字

---

## 管线（4 阶段）

```
S1  素材收集（collect.py 扫描 7 个 06_ai_daily.md）
    ↓
S2  模式识别（LLM 做共性提炼 + 弧线判断）
    ↓
S3  七日谈输出（严格格式，一次生成）
    ↓
S4  校验 + 存档（validate.py + archive.py，Harness 层）
```

---

## S1：素材收集

```bash
SKILL_DIR="${CLAUDE_SKILL_DIR:-$HOME/.claude/skills/ai-weekly}"
VAULT="${OBSIDIAN_VAULT:-/Users/admin/Documents/Obsidian Vault}"

# 收集过去 7 天的日报（默认昨天为结束日期）
python3 "$SKILL_DIR/scripts/collect.py"
```

**缺天处理：**
- ≥ 4 天：警告后继续，仅对有内容的天数做速览条目
- < 4 天：提示"素材不足，建议等更多日报生成后再运行"，但仍可强制继续

---

## S2：模式识别

读完 7 天素材后，在生成前回答以下 3 个问题（内部推理，不输出给用户）：

**Q1 — 本周反复出现了什么？**
扫描 7 天的「发生了什么」和「工具推荐」，找出：
- 同一公司/产品被提到 ≥ 2 次？
- 同一趋势词（降价/速度/法律/Agent/开源）出现 ≥ 3 次？
- 工具出现 ≥ 2 次？
→ 这是「本周共性」的候选

**Q2 — 本周有没有「故事弧线」？**
- 有没有事件在周初出现，周中发展，周末有结论？
- 有没有趋势从微弱变明显（如某公司从背景角色变主角）？
→ 这是「周度洞察」的素材来源

**Q3 — 普通人这周感受到了什么变化？**
- 有没有什么是「本周如果你用AI，你会感受到不同」？
- 哪件事下周可能还会继续发展、值得关注？
→ 用于「今周一句」的定性

---

## S3：七日谈输出

严格按照以下结构输出，不增减段落：

```
# AI七日谈 · 第X周（MM/DD-MM/DD）

今周一句：[一句话定性这周的走向，≤30字，有具体主语和方向，不写格言]
例：「七天里，AI从实验室走进了法庭、会议室和你的Word里」
例：「这周没有爆炸性发布，但速度、价格、开源三条线同时在动」

---

七日速览

MM/DD 周X：[当日最值得记的一件事，≤25字，只写事实+一句判断]
MM/DD 周X：[同上]
MM/DD 周X：[同上]
（重复7天，缺失天写「[无日报]」）

---

本周共性

▸ [主题词]：[2-3句，这一周反复出现的信号，说清楚出现了几次/怎么出现的]
▸ [主题词]：[同上]
（1-3条，没有共性不强行写；最多3条）

---

周度洞察

[60-150字。只写看完整周才能看见的东西：一个正在形成的趋势、一组彼此印证的信号、或一个本周才显形的转折。落脚到"对普通用户意味着什么"。不写每天都能写的观察。]

---

本周工具（可选）

[只在有工具被多天提及、或本周有特别值得长期关注的工具时写。没有则整段删除。]
工具名：[一句话，为什么本周特别值得关注]
```

---

## S4：校验 + 存档（Harness 层）

```bash
SKILL_DIR="${CLAUDE_SKILL_DIR:-$HOME/.claude/skills/ai-weekly}"
VAULT="${OBSIDIAN_VAULT:-/Users/admin/Documents/Obsidian Vault}"
DATE=$(date +%Y-%m-%d)
WEEK_NUM=$(date +%V)
YEAR=$(date +%Y)
WEEK_ID="${YEAR}-W${WEEK_NUM}"

# 临时输出文件
TMP_OUTPUT="/tmp/ai-weekly-${DATE}.md"

# [LLM 已将 S3 内容写入 $TMP_OUTPUT]

# Step 1: 格式校验
python3 "$SKILL_DIR/scripts/validate.py" "$TMP_OUTPUT"
VALIDATE_EXIT=$?

if [ $VALIDATE_EXIT -ne 0 ]; then
  echo "校验未通过，请根据提示修改后重新存档"
  # 展示内容给用户审阅
  exit 1
fi

# Step 2: 计算日期范围
END_DATE=$(date -v-1d +%Y-%m-%d 2>/dev/null || date -d "yesterday" +%Y-%m-%d)
START_DATE=$(date -v-7d +%Y-%m-%d 2>/dev/null || date -d "7 days ago" +%Y-%m-%d)
START_FMT=$(date -v-7d +%m/%d 2>/dev/null || date -d "7 days ago" +%m/%d)
END_FMT=$(date -v-1d +%m/%d 2>/dev/null || date -d "yesterday" +%m/%d)
DATE_RANGE="${START_FMT}-${END_FMT}"

# Step 3: 存档
python3 "$SKILL_DIR/scripts/archive.py" "$TMP_OUTPUT" \
  --week "$WEEK_ID" \
  --range "$DATE_RANGE"

echo "✓ AI七日谈 $WEEK_ID 已存档"
echo "路径：$VAULT/09_System/Automation/results/weekly/${WEEK_ID}-ai-weekly.md"
```

---

## 输出示例（风格参考）

```
# AI七日谈 · 第21周（05/12-05/18）

今周一句：七天里，Anthropic 从一家卖模型的公司，悄悄变成了一家卖基础设施的公司

---

七日速览

05/12 周一：Claude 速率翻倍，API 用户体感最直接的一次升级
05/13 周二：法律插件直插 Word/Outlook，AI 进入白领日常工具链
05/14 周三：DeepSeek 估值 500 亿，中国开源路线获资本认可
05/15 周四：Google I/O 预热，大模型发布潮进入卡位阶段
05/16 周五：何恺明小模型引发自回归路线讨论，学术界出现分歧
05/17 周六：[无日报]
05/18 周日：[无日报]

---

本周共性

▸ 速度/成本：Claude 提速、多家降价，模型性能竞争正在转向"更快更便宜"
▸ 行业垂直：法律、医疗、教育插件密集出现，AI 从通用到专业的落地在加速
▸ 开源博弈：DeepSeek、Llama 接连动作，中美开源竞争成为本周底色

---

周度洞察

这周如果你只看一天，会觉得"又是 Anthropic 的新功能"。但看完 7 天，会发现一个模式：
每一次发布都在解决"怎么让 AI 进入你已有的工作流"——不是新 App，是插件、API、提速。
Anthropic 在把门槛从"学会用新工具"降到"原来的工具里多了个 AI"。
这个方向一旦成立，改变的速度会比换 App 快得多。

---

本周工具

Claude Code /goal：本周 Anthropic 速率翻倍后，长任务自动执行的门槛明显降低，值得现在开始用
```

---

## 与 ai-daily 的关系

| 维度 | ai-daily | ai-weekly |
|------|----------|-----------|
| 数据源 | Morning Digest + aihot API | 7 × 06_ai_daily.md |
| 时间视角 | 今天发生了什么 | 这周形成了什么 |
| 核心输出 | 新鲜资讯 + 工具推荐 | 共性信号 + 趋势弧线 |
| 平台版本 | 公众号/X/小红书 三版 | 单一精炼版（公众号适配） |
| 字数 | ≤ 500 字 | ≤ 600 字 |
| Harness | validate.py + archive.py | collect.py + validate.py + archive.py |

ai-weekly 是 ai-daily 的上游归纳层，两者共用 `$OBSIDIAN_VAULT` 路径约定。

---

## 快速配置

与 ai-daily 共用同一个环境变量，无需额外配置：

```bash
# 在 ~/.zshrc 中（如果还没设置）
export OBSIDIAN_VAULT="/path/to/your/Obsidian Vault"
```
