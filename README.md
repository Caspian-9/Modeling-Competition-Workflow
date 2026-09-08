# 数学建模 FAST 工作区

面向全国大学生数学建模竞赛的本地 Skill-first 工作区。默认由一个持续主 Agent 完整理解题目、选择模型、解释实验并组织论文；Engineer、Librarian、Judge 按需调用。`harness/` 只负责可复现实验，不再编排 Agent 工作流。

## 当前状态

FAST 重构已替换原强治理 Harness：

| 能力 | 当前实现 |
|---|---|
| 主工作方式 | 用户与持续主 Agent 直接协作 |
| 角色调用 | Engineer、Librarian、Judge 按需；Writer 默认在主会话中启用 |
| 正式绘图 | 强制调用 Writer Figure Skill，再由其调用 `nature-figure` |
| 数据入口 | `cases/<CASE_ID>/raw/` |
| 初始化 | Q1 前完成数据预处理、EDA、中文 EDA 图和摘要前正文 |
| 实验内核 | manifest、输入 hash、seed、受控运行、日志、输出 hash |
| 并行实验 | `run-batch`，默认最多 8 个 worker |
| QC | 仅确定性运行与文件完整性检查 |
| 结果决策 | 主 Agent 推荐，用户最终决定，`selection.json` 留简洁理由 |
| 论文 | `paper/manuscript.md`，不接收 Harness 治理信息 |

详细决策和验收标准见 [plan.md](plan.md)。

## 工作流

```text
用户 + 主 Agent（连续会话）
  |
  |-- 读取题面和数据，维护 brief / symbols / progress
  |-- 按需 Librarian：外部事实、论文、标准、仓库
  |-- 按需 Engineer：EDA、预处理、模型、优化、验证
  |      `-- Thin Harness：experiment -> run -> deterministic QC
  |-- 主 Agent 比较结果并记录选择
  |-- 同一上下文启用 Writer Skill，持续写论文
  `-- 按需 Judge：重大歧义、关键方案、高风险结果、终稿
```

普通小问通常只有：

```text
主 Agent -> Engineer（必要时并行）-> 主 Agent 解释和选择 -> 写入论文
```

不再强制 `Judge -> Librarian -> Modeler -> Engineer -> Modeler -> Writer`，也不存在阶段状态机、Agent Job、staging、artifact registry、checkpoint 或后台 Supervisor。

## 目录结构

```text
.
|-- AGENTS.md                    # FAST 角色边界和不可破坏规则
|-- plan.md                      # 当前架构决策、实施计划与验收标准
|-- start-fast.ps1               # Windows 一键启动持续主 Agent
|-- harness/                     # 薄实验与归档内核
|   |-- cli.py                   # init/chat-intake/status/experiment/run/qc/select
|   |-- intake.py                # 附件复制、raw 清单、PDF 文本提取、XLSX 转 CSV
|   |-- runner.py                # 本地可信进程运行与最多 8 路并行
|   |-- process_control.py       # 超时、日志上限和 Windows 进程树回收
|   |-- qc.py                    # 确定性完整性检查
|   `-- tests/                   # FAST 回归测试
|-- cases/                       # 每道题的数据、分析、实验与论文
|-- 知识库/                      # 模型卡、统计检查卡、写作和评委规范
|-- 官方优秀论文（21-25）/       # 结构与论证质量参考
`-- .agents/skills/
    |-- orchestrate-modeling-work/       # 持续主 Agent
    |-- engineer-modeling-experiments/  # 按需实现与实验
    |-- research-modeling-literature/   # 按需证据检索
    |-- judge-modeling-work/             # 按需独立评审
    |-- write-modeling-paper/           # 同上下文论文写作
    `-- create-modeling-figures/        # Writer 专用中文科研绘图与 QA
```

新 FAST case：

```text
cases/<CASE_ID>/
|-- case.json
|-- raw/                         # 用户投放题目 PDF 和 XLSX/CSV，只读
|-- workspace/
|   |-- raw_inventory.json
|   |-- problem.md
|   |-- brief.md
|   |-- symbols.md
|   `-- progress.md
|-- initialization/
|   |-- plan.md                 # 主 Agent 的数据口径、清洗与 EDA 计划
|   |-- engineer_report.md      # Engineer 数据审计、预处理与 EDA 结果
|   |-- summary.md              # 主 Agent 的初始化总结
|   |-- front_matter.md         # Writer 摘要前正文，用户审阅后并入论文
|   `-- figures/                # Writer Figure Skill 生成的中文 EDA 图与 QA
|-- data/
|   |-- interim/
|   |   `-- raw_csv/                    # XLSX 各工作表自动导出的 UTF-8 CSV
|   `-- processed/
|-- questions/<Q>/
|   |-- analysis.md
|   |-- research/
|   |-- experiments/<EXP>/
|   |   |-- experiment.json
|   |   |-- code/
|   |   |-- outputs/
|   |   |-- runs/
|   |   `-- qc.json
|   |-- figures/
|   `-- selection.json
`-- paper/
    |-- manuscript.md
    |-- figures/
    |-- references.md
    `-- reviews/
```

历史 case 中原有的 `state/`、`agent_jobs/`、`checkpoints/` 等目录不会被删除，但 FAST 主 Agent 不读取它们。对历史 case 执行 `init` 会在原目录中增加 FAST 文件，不改写历史产物。

## 快速开始

### 桌面版推荐方式

在 ChatGPT 桌面版打开本工作区，直接开始一个新对话：

```text
我要开始一个数学建模 case。
```

主 Agent 会先询问 case ID。回复 ID 后，在下一条消息附加：

- 一份题目 PDF；
- 一个或多个 `.xlsx`、`.xls`、`.csv` 或 `.tsv` 数据文件。

Agent 随后会把当前会话的附件写入 `cases/<CASE_ID>/raw/`，调用 PDF 阅读能力复核题面，并自动把每个 `.xlsx` 工作表导出为 `data/interim/raw_csv/` 中的 UTF-8 CSV。原 PDF 和 XLSX 保留不变，`workspace/raw_inventory.json` 记录源文件、sheet、行列数、hash 和 CSV 路径。

若一开始已知道 ID，也可以直接写：

```text
启动数学建模 case 2025C-0903。我将在下一条消息附加题目 PDF 和数据。
```

如果桌面客户端没有把附件暴露给当前会话作为可读取文件，Agent 会要求重新附加或选择文件；不会要求改用终端。OpenAI 的 [桌面版文件工作流](https://learn.chatgpt.com/docs/artifacts-viewer) 说明桌面端可在对话旁预览 PDF、表格和文档；[文件输入文档](https://developers.openai.com/api/docs/guides/file-inputs) 确认 PDF、XLSX 和 CSV 都是支持的文件类型。

### 前置条件

- Windows PowerShell。
- Python 3.11+。
- 使用 ChatGPT 桌面版并打开本工作区。
- PDF 自动提取需要 `pypdf`；扫描版 PDF 仍需 OCR。
- XLSX 自动导出 CSV 需要 `openpyxl`。本工作区已验证该依赖可用；若桌面运行环境缺失，Agent 会给出明确缺失信息。

### 终端回退方式

在仓库根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-fast.ps1 -CaseId 2025C-0903
```

若省略 `-CaseId`，脚本会询问。该方式保留给无法使用桌面对话附件时的本地回退；新默认入口是上面的 ChatGPT 桌面版流程。

新 case 初始化后，把文件放入：

```text
cases/<CASE_ID>/raw/
|-- problem.pdf
`-- data.xlsx
```

再次执行 `start-fast.ps1`，主 Agent 会读取题面并开始工作。

### 手动 CLI 入口

```powershell
Set-Location 'C:\Users\yezf8\Desktop\Study\M_Research\数学建模'

python -m harness init 2025C-0903 --questions Q1 Q2 Q3 Q4
python -m harness intake 2025C-0903
python -m harness status 2025C-0903

codex --cd . --model gpt-5.6-terra -c 'model_reasoning_effort="high"'
```

进入 Codex 后说明当前 `case_id`。Agent 会先读取 `AGENTS.md` 与主 Agent Skill。

桌面附件对应的底层命令为，通常由 Agent 自动调用，无需用户手工执行：

```powershell
python -m harness chat-intake 2025C-0903 `
  --file <ATTACHED_PROBLEM.pdf> `
  --file <ATTACHED_DATA.xlsx>
```

## 实验命令

创建实验时，`--command` 必须放在最后：

```powershell
python -m harness experiment-create 2025C-0903 Q1 EXP-BASE `
  --title "可解释基线" `
  --objective "建立可解释基线并验证主要关系" `
  --seed 2026 `
  --input raw/data.xlsx `
  --output outputs/metrics.json `
  --output outputs/report.md `
  --command python code/main.py
```

脚本写入：

```text
cases/2025C-0903/questions/Q1/experiments/EXP-BASE/code/main.py
```

运行、检查并记录选择：

```powershell
python -m harness run 2025C-0903 Q1 EXP-BASE
python -m harness qc 2025C-0903 Q1 EXP-BASE
python -m harness select 2025C-0903 Q1 EXP-BASE --reason "结果稳定、解释清晰且直接回答问题"
```

并行运行多个已创建实验：

```powershell
python -m harness run-batch 2025C-0903 Q1 EXP-A EXP-B EXP-C --max-workers 8
```

实验进程可读取以下环境变量：

- `MODELING_CASE_DIR`
- `MODELING_RAW_DIR`
- `MODELING_DATA_DIR`
- `MODELING_EXPERIMENT_DIR`
- `MODELING_OUTPUT_DIR`
- `MODELING_SEED`

`run` 使用 `shell=False`、可执行文件白名单、运行超时和日志上限，并在 Windows 下回收整个进程树。它不是安全沙箱，只用于可信代码。

`qc` 检查最近一次运行、输入 hash、代码 hash 和声明输出 hash。`PASS` 不代表模型合理或论文结论正确。用户确需采用未通过确定性 QC 的结果时可使用 `select --force`，原 QC 结果仍保留。

## 按需调用角色

可以在主会话中直接提出：

- “调用 Engineer 对 Q2 实现两个可比基线并运行。”
- “调用 Librarian 核验这个医学阈值的权威来源。”
- “调用 Judge 独立审查当前 Q3 是否存在数据泄漏。”
- “使用 Writer Skill 把 Q1 分析整理进论文，并删除工程报告口吻。”

不调用的角色不产生 token 成本。

## 图表

任何 EDA、结果或论文图都必须经 Writer Figure Skill：

```text
主 Agent 定义结论和数据边界
  -> $create-modeling-figures
  -> ModelViz 可选召回候选图型
  -> $nature-figure 基于真实数据原创中文多面板重绘
  -> 实际查看最终图像并做字体、碰撞、单位和叙事 QA
```

图型召回不是模板代码复用，绘图工具不得新增统计结论或改变数据筛选口径。正式图、脚本和简洁来源说明保存在当前问 `figures/` 或 `paper/figures/`。

## 初始化

raw intake 后、Q1 前默认完成一次共享初始化：

```text
主 Agent：initialization/plan.md
  -> Engineer：数据审计、预处理、EDA 源数据与 engineer_report.md
  -> 主 Agent：summary.md
  -> Writer Figure Skill：initialization/figures/ 中文 EDA 图
  -> Writer：front_matter.md（不含摘要与各问结果）
  -> 用户审阅
  -> Q1
```

使用 `python -m harness status <CASE_ID>` 可查看 `initialization.status` 及缺失产物。它依次显示 `WAITING_FOR_RAW`、`NOT_STARTED`、`ENGINEERING`、`SYNTHESIS`、`FIGURES`、`WRITING` 和 `READY_FOR_Q1`，不引入独立状态机或后台服务。

## 验证

```powershell
python -m compileall -q harness
python -m unittest discover -s harness/tests -v
python -m harness --help
```

## 数据与许可

`raw/` 默认不提交 Git。仓库中的官方论文、格式文件和外部模板整理副本保留各自来源与许可约束；公开分发或再利用前需核对授权。
