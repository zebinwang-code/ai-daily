# ai-daily — AI 日报 & 七日谈 Claude Skill

> 从晨报到三平台发布，再到周度共性提炼的完整 AI 内容生产管线。  
> 日报（`/ai-daily`）+ 周报（`/ai-weekly`），同一套 Harness 架构的两个时间粒度。

## 两个入口

| 命令 | 频率 | 输出 | 字数 |
|------|------|------|------|
| `/ai-daily` | 每天 | 公众号 / X / 小红书 三版日报 | ≤ 500 字/版 |
| `/ai-weekly` | 每周 | AI七日谈，共性信号 + 趋势弧线 | ≤ 600 字 |

周报读取过去 7 天的日报文件作为素材，两者共用 `$OBSIDIAN_VAULT` 路径约定。

---

## 文件结构

```
ai-daily/
├── SKILL.md                          # /ai-daily 主 Skill（日报管线）
├── SKILL-weekly.md                   # /ai-weekly 主 Skill（七日谈管线）
│
├── scripts/                          # 日报 Harness 脚本
│   ├── validate.py                   # 格式校验（字数/结构/禁止词）
│   ├── title-score.py                # 标题五维度评分（0-10分）
│   ├── archive.py                    # 知识库归档 + 自进化蒸馏
│   └── feed-update.py                # 创作者素材抓取（公众号 + XHS CDP）
│
├── weekly-scripts/                   # 七日谈 Harness 脚本
│   ├── collect.py                    # 扫描 7 天日报，结构化输出
│   ├── validate.py                   # 周报格式校验
│   └── archive.py                    # 存档到 weekly/ + 维护周索引
│
└── references/
    ├── platform-voices.md            # 三平台风格规则（公众号/X/小红书）
    ├── creator-config.json           # 标杆创作者配置
    └── xhs-image-template.md         # 小红书封面图模板
```

---

## 日报管线（`/ai-daily`）

**数据源优先级：**

| 优先级 | 来源 | 说明 |
|--------|------|------|
| **主源** | `03_Resources/_Morning/YYYY-MM/YYYY-MM-DD-Digest.md` | resource-morning 管道每日生成，聚合多源 + hot_score |
| **Fallback** | [aihot API](https://aihot.virxact.com/api/public/daily) | Digest 未生成时使用，无需 Key |

**六阶段管线：**
```
S0  创作者素材更新（24h TTL）
S1  素材收集（Morning Digest 主源 + aihot fallback）
S2  蒸馏提炼（普通人视角三问过滤 + 工具优先级）
S3  三版并行输出（标题竞选 ≥7/10 先行）
S3.5 双重校验（validate.py + title-score.py）
S4  存档（archive.py，每7次触发风格蒸馏）
```

**选题原则（普通人优先）：**  
判断标准：「不做 AI 的人看完，能知道这件事跟自己有没有关系吗？」  
优先选影响日常工具/价格/工作方式的故事，纯融资/论文/行业内部新闻次之。

**配图（S5）：** 每日 4 张竖版图（ChatGPT CDP 生成）

| 图 | 内容 |
|----|------|
| `img_cover.png` | 今日主题艺术图，`MMDD AI观察` |
| `img_card1/2.png` | 最重要变化解说卡，普通人视角 |
| `img_reflection.png` | 日有所思心得卡 |

---

## 周报管线（`/ai-weekly`）

**核心理念：** 周报 ≠ 日报 × 7。找出只有看完整周才能看见的信号。

**数据源：** 过去 7 天的 `09_System/Automation/results/YYYY-MM-DD/06_ai_daily.md`

**四阶段管线：**
```
S1  collect.py 扫描 7 个日报文件
S2  LLM 模式识别（三问：反复出现了什么？有故事弧线吗？普通人感受到什么？）
S3  七日谈输出（今周一句 / 七日速览 / 本周共性 / 周度洞察）
S4  validate.py 校验 + archive.py 存档到 weekly/
```

**输出路径：** `$OBSIDIAN_VAULT/09_System/Automation/results/weekly/YYYY-WXX-ai-weekly.md`

---

## 安装

```bash
git clone https://github.com/zebinwang-code/ai-daily ~/.claude/skills/ai-daily
```

在 `~/.zshrc` 中设置 Vault 路径：

```bash
export OBSIDIAN_VAULT="/path/to/your/Obsidian Vault"
```

**前提条件：** Claude Code CLI · Python 3.8+ · CDP Proxy（`localhost:3456`，XHS/图片功能需要）

**路径说明：**

| 用途 | 路径 |
|------|------|
| 日报数据源 | `$OBSIDIAN_VAULT/03_Resources/_Morning/YYYY-MM/YYYY-MM-DD-Digest.md` |
| 日报输出 | `$OBSIDIAN_VAULT/09_System/Automation/results/YYYY-MM-DD/06_ai_daily.md` |
| 周报输出 | `$OBSIDIAN_VAULT/09_System/Automation/results/weekly/YYYY-WXX-ai-weekly.md` |

---

## 架构模式（[[Harness]]）

```
           Morning Digest / aihot API
                    ↓
         ┌──────────────────────┐
         │    /ai-daily (LLM)   │  ← Model 层：蒸馏 + 生成
         └──────────────────────┘
                    ↓
    validate.py · title-score.py · archive.py   ← Harness 层：确定性执行
                    ↓
         06_ai_daily.md × 7天
                    ↓
         ┌──────────────────────┐
         │   /ai-weekly (LLM)   │  ← Model 层：共性提炼 + 弧线
         └──────────────────────┘
                    ↓
    collect.py · validate.py · archive.py        ← Harness 层
                    ↓
         YYYY-WXX-ai-weekly.md
```

LLM 负责判断和生成，脚本负责文件 I/O、格式校验、存档——两层职责不交叉。

---

## License

MIT
