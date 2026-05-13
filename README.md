# ai-daily — 每日 AI 日报 Claude Skill

> 从 Morning Digest + aihot 到三平台发布就绪内容的全自动生产管线，内置质量校验和自进化机制。

## 一句话定位

每天一次 `/ai-daily`，自动输出**公众号 / X / 小红书**三版 AI 日报，500字以内，格式校验通过才算完成。

## 功能亮点

- **六阶段管线**：素材收集 → 蒸馏提炼 → 标题竞选 → 三版并行输出 → 双重校验 → 存档
- **五维质量控制**：标题评分（5维度 ≥7/10）+ 选题三问 + 字数/结构校验 + 排版规范 + XHS封面图
- **自进化机制**：每次运行自动归档到 knowledge-base，每7次触发蒸馏提示更新风格规则
- **多 Agent 接口**：支持 `--date`/`--platforms`/`--dry-run`/`--output-json` 参数，可作为子模块调用

## 文件结构

```
ai-daily/
├── SKILL.md                          # 主 Skill 文件（Claude Code 加载入口）
├── scripts/
│   ├── validate.py                   # 格式校验（字数/结构/禁止词）
│   ├── title-score.py                # 标题五维度评分（0-10分）
│   ├── archive.py                    # 知识库归档 + 自进化蒸馏
│   └── feed-update.py                # 创作者素材抓取（公众号 Sogou + XHS CDP）
└── references/
    ├── platform-voices.md            # 三平台风格规则（公众号/X/小红书）
    ├── creator-config.json           # 标杆创作者配置（歸藏/宝玉xp/赛博禅心等）
    └── xhs-image-template.md         # 小红书封面图模板（3种风格 + 生成指令）
```

## 数据源

| 优先级 | 来源 | 说明 |
|--------|------|------|
| **主源** | `03_Resources/_Morning/YYYY-MM/YYYY-MM-DD-Digest.md` | resource-morning 管道每日生成，聚合多源 + hot_score + OKR 分析 |
| **Fallback** | [aihot API](https://aihot.virxact.com/api/public/daily) | Digest 未生成时使用，无需 Key |

## 六阶段管线

```
S0  创作者素材更新（24h TTL，CDP 抓取 XHS）
    ↓
S1  素材收集（Morning Digest 主源 + aihot fallback）
    ↓
S2  蒸馏提炼（三问过滤 + 灵感类型判定 + 工具优先级）
    ↓
S3  三版并行输出（S3.0 标题竞选先行，≥7/10 才写正文）
    ↓
S3.5 双重校验（validate.py 格式 + title-score.py 标题）
    ↓
S4  存档（archive.py，每7次触发蒸馏提示）
```

## 标题评分维度（title-score.py）

各维度 0-2 分，满分 10，通过线 ≥7：

| 维度 | 信号示例 |
|------|---------|
| 情绪钩子 | 「居然/终于/坏了/在浪费」 |
| 具体锚点 | 数字/时间/品牌名 |
| 读者利益 | 「你/省/教程/怎么」 |
| 张力悬念 | 反差/疑问/「同一天/但/却」 |
| 精准不废话 | ≤20字，无套话 |

## 参考标杆创作者

| 创作者 | 平台 | 风格 |
|--------|------|------|
| 歸藏 | 公众号 + XHS | 工具快讯，功能+判断同时给出 |
| 宝玉xp | 公众号 | 模型/研究层解读 |
| 赛博禅心 | 公众号 + XHS | 安静洞察，第一人称真实感 |
| 卡兹克 | 公众号 + XHS | 具体数据，游戏化叙事 |
| 花叔 | 公众号 + XHS | 毒舌类比，视觉化表达 |
| 刘小排 | 公众号 + XHS | 极端对比，立场鲜明 |

## 安装 & 配置

### 1. 克隆到 Claude Code skills 目录

```bash
git clone https://github.com/zebinwang-code/ai-daily ~/.claude/skills/ai-daily
```

### 2. 设置 Obsidian Vault 路径

在 `~/.zshrc`（或 `~/.bashrc`）中添加：

```bash
export OBSIDIAN_VAULT="/path/to/your/Obsidian Vault"
```

然后 `source ~/.zshrc`。Skill 所有路径都从这个变量派生，换机只需改这一处。

### 3. 前提条件

- Claude Code CLI
- Python 3.8+
- CDP Proxy（XHS 创作者素材抓取需要，`localhost:3456`；不需要 XHS 功能可跳过）

### 路径说明

| 用途 | 路径 |
|------|------|
| 主数据源 | `$OBSIDIAN_VAULT/03_Resources/_Morning/YYYY-MM/YYYY-MM-DD-Digest.md` |
| 日报输出 | `$OBSIDIAN_VAULT/09_System/Automation/results/YYYY-MM-DD/06_ai_daily.md` |

## 架构模式

本 Skill 实现了 [[Harness]] 模式：
- **Model 层**：LLM 负责蒸馏判断和内容生成
- **Harness 层**：`validate.py` + `archive.py` 负责确定性执行，不依赖 LLM 判断

## License

MIT
