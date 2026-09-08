# FAST 工作流重构计划

更新日期：2026-09-04

状态：**已完成**

2026-09-07 桌面对话附件入口：**已完成**

## 决策

项目默认采用 `Skill-first + Thin Harness`，不再运行强制的
`Judge -> Librarian -> Modeler -> Engineer -> Modeler -> Writer` 状态机。

- 用户直接交互的 Codex 会话是持续工作的主 Agent，同时负责题意理解、建模决策、结果解释和论文组织。
- Engineer、Librarian、Judge 按实际需要调用；Writer 默认作为主 Agent 在同一上下文中启用的写作 Skill，而不是独立交接 Job。
- Harness 只负责确定性机械工作：case 初始化、raw 文件登记、实验 manifest、受控运行、并行运行、确定性 QC、结果选择记录和进度汇总。
- Harness 运行元数据只保存在实验 sidecar 文件中，不得进入论文正文。
- 历史 `cases/` 不迁移、不改写；新 CLI 能以只读方式识别旧 case，并允许在其中创建 FAST 工作区。

## FAST 主流程

```text
用户 + 主 Agent（连续会话）
  |-- 读取题面与数据，维护 workspace/brief.md、symbols.md、progress.md
  |-- 按需调用 Librarian：领域事实、论文、标准、代码线索
  |-- 按需调用 Engineer：EDA、预处理、模型、验证、优化
  |     `-- Thin Harness：manifest -> run -> deterministic QC
  |-- 主 Agent 比较结果并记录 selection.json
  |-- 在同一上下文启用 Writer Skill，持续写 paper/manuscript.md
  `-- 按需调用独立 Judge：关键方案、风险结果、终稿
```

默认每小问只有：

```text
主 Agent -> Engineer（必要时并行）-> 主 Agent 解释与选择 -> 写入论文
```

## 新目录约定

```text
cases/<case_id>/
|-- case.json                    # 最小 case 信息，无阶段状态机
|-- raw/                         # 用户原始题面和数据，只读
|-- workspace/
|   |-- raw_inventory.json       # hash、格式和题面提取状态
|   |-- problem.md               # 从 PDF 提取的题面
|   |-- brief.md                 # 主 Agent 的题意与总体思路
|   |-- symbols.md               # 全文符号表
|   `-- progress.md              # 面向用户的简洁进度
|-- data/
|   |-- interim/
|   `-- processed/
|-- questions/<Q>/
|   |-- analysis.md              # 当前问连续推理与结论
|   |-- research/                # 按需检索结果
|   |-- experiments/<EXP>/
|   |   |-- experiment.json
|   |   |-- code/
|   |   |-- outputs/
|   |   |-- runs/
|   |   `-- qc.json
|   |-- figures/
|   `-- selection.json           # 当前采用结果及理由
`-- paper/
    |-- manuscript.md
    |-- figures/
    |-- references.md
    `-- reviews/
```

## 实施步骤

1. **最小合同和 CLI**：完成 FAST case、raw inventory、experiment、run、QC、selection 的数据模型和命令设计。
2. **薄 Harness**：重写 `harness/`，保留 Windows 进程树超时回收，移除状态机、Agent Dispatcher、Dashboard、checkpoint、artifact registry、staging promotion 和 literature pipeline。
3. **Skill-first 角色**：重写主 Agent、Engineer、Writer、Librarian、Judge Skill；删除 Supervisor Skill。所有角色默认中文，按需读取知识，不再要求 JSON handoff。
4. **入口与文档**：新增根目录 `start-fast.ps1`，重写 README、Harness README、case 模板和 `AGENTS.md`。
5. **清理与验证**：删除旧 schema、examples 和测试，建立覆盖新 CLI、intake、runner、QC、batch、selection 的测试；运行 Skill 校验、`compileall` 和 `unittest`。

## 验收标准

- 新 case 只需执行一次初始化并把 PDF、XLSX/CSV 放入 `raw/`。
- 主 Agent 不依赖中央状态机即可从题面持续工作到论文完成。
- 单个实验可记录输入 hash、命令、seed、退出码、耗时、日志和输出 hash。
- 多实验可在一个命令中并行运行，默认最多 8 个 worker。
- QC 只报告确定性完整性，不冒充语义或建模质量评审。
- Writer 默认不读取 `runs/`、`qc.json` 或 Harness 日志；论文中不得出现 Job、artifact、staging、QC 状态等内部治理语言。
- Judge 和 Librarian 未被需要时不产生任何调用与 token 成本。
- `python -m unittest discover -s harness/tests -v` 全部通过。

## 非目标

- 不迁移或清理历史 case 产物。
- 不提供后台 Supervisor、Dashboard 或 Agent 自动恢复。
- 不强制 tournament、固定候选数量、固定论文槽位或逐阶段审批。
- 不用 Harness 代替主 Agent 的建模判断、论文审校或用户最终决策。

## 完成记录

- 已将 CLI 收缩为 `init`、`intake`、`status`、`experiment-create`、`run`、`run-batch`、`qc` 和 `select`。
- 已删除旧状态机、Agent Dispatcher、Dashboard、checkpoint、artifact registry、staging、literature pipeline、旧 schema 和对应测试。
- 已将交互默认角色改为持续主 Agent，删除 Supervisor Skill；Engineer、Librarian、Judge 改为按需调用，Writer 默认在主会话中使用。
- 已增加论文上下文隔离，禁止 Writer 消费旧状态、Agent 日志、运行日志和治理字段。
- 已保留 Windows 进程树超时回收，并使实验子进程不继承 API key 等凭据。
- 已新增根目录 `start-fast.ps1` 和完整快速开始文档。
- 验证通过：5 个 Skill quick validation、PowerShell 语法检查、`ruff`、`compileall` 和 14 项单元测试。

## 桌面对话附件入口

目标：在 GPT 桌面版对话中询问 case ID 与附件，由主会话将用户明确附加的题目和数据交给 Harness；不要求用户使用终端。

1. 新增 `chat-intake`：初始化或打开 case，复制附件至 `raw/`，登记 hash 后运行常规 intake。
2. 题面 PDF 由当前会话 PDF 能力复核，`workspace/problem.md` 保留可恢复文本。
3. `.xlsx` 自动按工作表导出 UTF-8 CSV 至 `data/interim/raw_csv/`，并在 raw inventory 记录源文件、sheet、行列数和 hash。
4. 更新主 Agent Skill、AGENTS、README 和 case 模板，明确桌面对话的询问、附件、异常与论文隔离规则。
5. 新增附件复制和 XLSX 多工作表转换测试，运行全量验证。

完成记录：已新增 `chat-intake`，主 Agent 会在桌面对话中询问 case ID 与附件；PDF 由 `$pdf` Skill 复核，XLSX 由 `$spreadsheets` Skill 检查并自动导出 CSV。`ruff`、`compileall`、主 Agent Skill 校验、PowerShell 语法检查和 16 项单元测试均通过。
