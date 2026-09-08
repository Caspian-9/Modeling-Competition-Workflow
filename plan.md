# FAST 工作流重构计划

更新日期：2026-09-08

状态：**FAST 重构与本轮探索检验闭环修正已完成；真实答题效果评测待开展**

## 当前修正计划：探索、检验与知识入口

目标：规范证据责任而不限定模型答案，保持 Skill-first + Thin Harness，不恢复逐阶段审批。

1. [已完成] 核对现有规范与实现，保留历史完成记录，明确本轮修改范围。
2. [已完成] 在根约定和主 Agent、Engineer、Writer Skill 中落实探索、假设、验证设计、实验、反证与修正；明确允许库外方法。
3. [已完成] 新增轻量问题驱动知识入口和探索、检验卡；按用户最新要求直接清理冲突规则，保留有效方法、案例和来源资产。
4. [已完成] 增强新 case 的 analysis.md 模板，保留既有文件；添加模板内容与非覆盖回归测试。
5. [已完成] 运行编译与单元测试，检查规范引用和修改范围，回写实际完成结果。

验收：探索留下“发现 → 模型影响”；模型实现前确定验证方案；结论采用前记录证据、失败处置与剩余风险；未检查不等于通过，不适用需解释；QC 不认定建模有效。

范围：本轮不修改历史 cases，不增加向量数据库、状态机、固定候选数、强制 Judge 或语义自动评分。知识入口只按问题触发少量卡片。

后续效果评测（本轮不宣称完成）：选择旧题片段，在固定模型配置与预算下重复比较改造前后关键结构发现、检验遗漏、错误结论修正和时间成本。真实 Agent 行为改善须由该评测确认，单元测试不能证明。

Harness 证据缺口自动提示暂缓：先稳定自然语言模板与实际使用方式，避免以标题存在或填表完整冒充科学有效性。

### 2026-09-08 实施结果

- 更新根 AGENTS.md 和主 Agent、Engineer、Writer 三个 Skill，明确探索证据、事前验证设计、失败处置、库外方法与知识按需读取。
- 新增问题驱动入口及 E01 建模前探索、E02 信息边界与验证设计、V01 主张与检验证据三张卡；标明内部工作约定与来源状态，未将其伪称为已核验学术来源。
- 知识库 README 已重写为当前使用指南；旧门禁、Dify 和交接内容按用户最新要求直接修改或删除，不再保留冲突正文。
- 增强 storage.py 的新分析模板及 Harness 使用说明，不改变 QC/select 语义，不改写历史 cases。
- 新增 3 项回归测试：新模板责任覆盖、重复初始化保持原始字节、历史分析保留且缺失小问获得新模板。
- 验证通过：3 项定向测试、20 项全量单元测试、compileall、修改 Python 文件的 ruff、3 个 Skill quick validation、知识入口 5 项路径检查和修改范围内 git diff --check。Skill 校验使用 Python UTF-8 模式以避免 Windows 默认 GBK 解码错误。
- 上述验证仅确认实现与文件规范，不证明 Agent 已在真实比赛中稳定执行或提升模型质量；后续效果评测与自动提示仍按前述边界保留。

### 2026-09-08 知识库冲突直接清理

用户决策：知识库不必保留与现行流程冲突的历史版本，可直接改写或删除。此决策仅针对知识规则，不清理历史 case、原始资料或用户实验。

- [已完成] 重写知识库 README，删除旧工作流、阶段审批和建设任务正文。
- [已完成] 将 J03 阶段门禁改为按需质量检查、J07 固定 Schema 改为自然语言反馈指南；修订 J01/J02/J04/J06 和 W05，取消固定候选数、评审状态与强制登记，保留证据底线。
- [已完成] 删除废弃 Dify 配置和导入 manifest；导入清单改为案例读取指南，WR05 改为外部模板使用边界，同步知识索引和来源说明。
- [已完成] 删除会批量覆盖维护卡片并重新生成旧规则的 build_phase2.py；保留现有模型卡。修改 build_phase1.py 的指南输出，未运行语料重建。
- [已完成] 同步主 Agent Skill 和问题入口，明确冲突直接修正，不以历史参考方式保留矛盾执行要求。
- [已完成] 检查通过：知识索引93处和问题入口5处引用、94个卡片ID唯一性及元数据解析、剩余知识脚本语法、案例读取指南与生成器一致性、受维护知识中的旧规则及旧路径扫描、主 Skill 校验、git diff --check。

未修改案例正文、外部克隆仓库、原始附件或当前初始化实现；本次没有重跑建模实验，也不声称已完成真实答题效果评测。

2026-09-07 桌面对话附件入口：**已完成**

2026-09-08 初始化闭环：**已完成**

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

## 初始化闭环

目标：在 FAST workflow 中恢复 case 级数据预处理与数据探索，但保持无状态机、无 tournament 的轻量形态。

1. 新 case 创建 `initialization/`，包含计划、Engineer 报告、主 Agent 总结、中文 EDA 图和摘要前正文的稳定路径。
2. `status` 确定性汇报初始化缺失产物与阶段，不以空文件、聊天记忆或 Job 记录判断完成。
3. 主 Agent 默认在 Q1 前完成初始化；Engineer 负责数据预处理与 EDA 源数据，Writer Figure Skill 负责正式 EDA 图，Writer 负责 `front_matter.md`，用户审阅后推进。
4. 为目录和状态推进增加回归测试，并同步更新各角色 Skill 和文档。

完成记录：已创建轻量 `initialization/` 闭环，覆盖共享数据预处理、EDA 源数据、正式中文 EDA 图与摘要前正文。`status` 以非空真实产物确定性显示 `WAITING_FOR_RAW` 至 `READY_FOR_Q1` 的阶段和缺失项；主 Agent、Engineer、Writer 与 Figure Skill 已同步适配，且不恢复旧 Harness 的状态机或 tournament。已有 FAST case 在下次加载时只补齐缺失的初始化脚手架，不改写已有产物。验证通过：21 项单元测试、`ruff check harness`、`compileall`、4 个关联 Skill 结构校验和 `git diff --check`。
