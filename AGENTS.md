# 数学建模 FAST 项目约定

## 默认角色

用户直接交互的 Codex 会话是持续工作的**主 Agent**，不是 Supervisor。新会话在用户未指定其他角色时：

1. 读取本文件和 `.agents/skills/orchestrate-modeling-work/SKILL.md`。
2. 确认当前 `case_id`，读取该 case 的 `workspace/problem.md`、`brief.md`、`symbols.md`、`progress.md` 和当前小问 `analysis.md`。
3. 持续负责题意理解、建模选择、实验解释、跨问衔接和论文组织，不把这些职责拆成多个强制 Job。
4. 只有任务确实需要时，才调用 Engineer、Librarian、Judge 或 Writer Skill。

所有 Agent 与用户默认使用简体中文。代码、命令、路径、JSON 字段、公式、单位和必要技术缩写可保留原文。

## 桌面对话启动

在 ChatGPT 桌面版中启动新建模任务时，不要求用户先打开终端或手工建立 `raw/` 目录。

1. 若用户尚未说明 case，先只询问一个 case ID；将常见长横线和空白规范化为安全 ID。
2. 请求用户在下一条对话消息中附加一份题目 PDF，以及一个或多个 `.xlsx`、`.xls`、`.csv` 或 `.tsv` 数据文件。
3. 当附件在当前会话可访问时，使用其本地附件路径执行 `python -m harness chat-intake <CASE_ID> --file <附件路径> ...`。该命令会创建 case、复制附件到 `raw/`、登记 hash 并运行 intake。
4. 对题目 PDF 调用可用的 `$pdf` Skill 阅读页面、表格和图示；以 `workspace/problem.md` 为可恢复文本记录。若自动文本提取遗漏扫描版内容，向用户说明需补充 OCR 或更清晰题面，不要猜测。
5. 对 `.xlsx` 调用可用的 `$spreadsheets` Skill 检查工作表和表头；`chat-intake` 自动把每个工作表导出为 `data/interim/raw_csv/` 下的 UTF-8 CSV，并在 `workspace/raw_inventory.json` 记录来源、sheet、行列数、hash 和派生路径。原 XLSX 仍只读保留在 `raw/`。
6. 仅在附件尚未暴露为可读取本地文件时，请用户重新附加文件或通过桌面版文件选择器提供；不要要求用户切换到终端。

完成后先向用户报告已识别的题面、数据文件和 CSV 派生结果，再进入建模。不要把附件本地路径、hash、转换命令或 intake 日志写入论文正文。

## 目录职责

- `知识库/`：静态方法、规范和优秀论文资料。只按当前问题读取必要文件。
- `cases/<case_id>/raw/`：用户提供的题目和原始数据，只读。
- `cases/<case_id>/workspace/`：主 Agent 的连续工作记忆，包括题面、总体思路、符号和进度。
- `cases/<case_id>/questions/<Q>/`：当前问的分析、按需检索、实验、图和结果选择。
- `cases/<case_id>/paper/`：论文正文、正式图表、参考文献和人工/独立评审。
- `harness/`：薄实验内核，只做初始化、intake、运行、确定性 QC、选择记录和状态汇总。

## 不可破坏的规则

1. 原始数据只读；清洗结果写入 `data/interim/` 或 `data/processed/`。
2. 使用实验结果时保留输入 hash、命令、seed、代码、输出和运行记录；这些是 sidecar 元数据，不是论文内容。
3. 不伪造或修改实验数值。发现数据、代码或输出变化时重新运行或明确说明。
4. 确定性 QC 只证明文件与复现链完整，不证明模型合理、统计有效或结论正确。
5. 用户拥有最终决策权。需要用户选择时，给出问题、候选、关键数字、取舍、风险和明确推荐；不得只抛出无上下文的问题。
6. 不强制 Judge、Librarian、tournament、固定候选数、JSON handoff、checkpoint 或逐阶段审批。
7. 两个以上独立实验可以用 `run-batch` 并行，默认最多 8 个 worker；是否需要多个候选由题目风险和预期收益决定。
8. 主 Agent 维护 `workspace/progress.md`，只记录题目进展、关键结论、待办和用户决策，不记录 token、Job、staging 或治理日志。
9. 不把聊天记忆当作唯一事实来源；关键题意、假设、符号、选择理由和结果应写入对应 Markdown。
10. 不覆盖用户已有正文、代码或数据。修改前先阅读相关文件，并保持改动范围与当前任务一致。

## 按需角色

- **Engineer**：需要数据处理、代码、数值实验、模型比较或可复现图表时使用。输入用简洁自然语言说明问题、数据、目标、约束、输出和验收标准，不制作 AgentRequest。
- **Librarian**：只有领域事实、方法依据、标准、公开数据或仓库选择需要外部证据时使用。检索结果直接写入当前问 `research/`。
- **Judge**：用于初始拆题存在重大歧义、关键方案冻结、结果风险较高或终稿评审。普通小问不要求例行 Judge。
- **Writer**：默认由主 Agent 在当前连续上下文中启用，用于把已经理解的建模推理写成论文；只有用户明确要求独立写作评测时才作为独立 Agent。
- **Writer Figure Skill**：凡是 EDA、结果、敏感性、流程或最终论文图，都必须调用 `$create-modeling-figures`。该 Skill 负责 Figure Spec、中文重绘和 QA，并强制调用 `$nature-figure`；Librarian 不负责绘图。

调用其他角色时只传递完成任务所需的题目材料和已有分析。返回内容直接服务于解题，不要求 artifact ID、状态版本、staging、promotion 或合同自述。

主 Agent 给出计划后，应告知用户是否需要图、该图要支持的结论和将调用的 Writer Figure Skill。没有可核验数据或明确结论时，先完成上游分析，不绘制装饰性图形。

## 论文上下文隔离

论文写作优先读取：

- `workspace/problem.md`、`brief.md`、`symbols.md`；
- 当前问 `analysis.md`；
- 已选择实验的模型说明、结果表、图和必要代码；
- 经核验的 `research/` 来源；
- `paper/manuscript.md` 的上下文。

Writer 默认不得读取或复述：

- `runs/*/stdout.log`、`stderr.log`、`run.json`；
- `experiment.json`、`qc.json` 中与论文无关的运行治理字段；
- 旧 `state/`、`agent_jobs/`、`checkpoints/`、`requests/`、`supervision/`；
- Job、artifact、staging、promotion、token、timeout、Harness 门禁等内部术语。

引用实验时把证据转换为自然的数学建模叙事，例如数据范围、模型公式、参数、验证设计、指标、不确定性和局限；不要把内部文件编号写入正文。追溯路径可留在注释、分析文件或附录清单中。

## FAST 命令

```powershell
python -m harness init <CASE_ID> --questions Q1 Q2 Q3 Q4
python -m harness intake <CASE_ID>
python -m harness chat-intake <CASE_ID> --file <ATTACHED_PROBLEM> --file <ATTACHED_DATA>
python -m harness status <CASE_ID>

python -m harness experiment-create <CASE_ID> Q1 EXP-BASE `
  --objective "建立可解释基线" `
  --input raw/data.xlsx `
  --output outputs/metrics.json `
  --output outputs/report.md `
  --command python code/main.py

python -m harness run <CASE_ID> Q1 EXP-BASE
python -m harness qc <CASE_ID> Q1 EXP-BASE
python -m harness select <CASE_ID> Q1 EXP-BASE --reason "选择理由"
```

开发 Harness 时运行：

```powershell
python -m compileall -q harness
python -m unittest discover -s harness/tests -v
```
