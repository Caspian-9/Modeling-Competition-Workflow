# FAST Harness

本目录是数学建模工作区的薄实验内核，不负责 Agent 编排、论文写作、阶段审批或后台监控。

## 命令

| 命令 | 作用 |
|---|---|
| `init` | 创建 FAST case 目录和连续工作文件 |
| `intake` | 登记 `raw/` 文件 hash、检查数据格式并提取题面 |
| `chat-intake` | 接收桌面对话附件、复制到 `raw/`、登记题面和数据，并将 XLSX 工作表导出为 CSV |
| `status` | 汇总原始输入、实验、选择和论文文件 |
| `experiment-create` | 固定输入 hash、命令、seed 和声明输出 |
| `run` | 在实验目录运行一个可信命令 |
| `run-batch` | 最多 8 路并行运行独立实验 |
| `qc` | 检查运行、输入、代码和输出完整性 |
| `select` | 记录当前问采用的实验及自然语言理由 |

完整示例见根目录 [README](../README.md)。

## 设计边界

- 没有中央状态机、Agent Job、checkpoint、artifact registry 或 staging。
- 每个实验独立写自己的目录，批量运行无需共享写锁。
- `run.json`、日志、`experiment.json` 和 `qc.json` 是复现 sidecar，不是 Writer 输入。
- `chat-intake` 只复制用户明确附加的文件；同名不同内容默认拒绝，必须显式 `--replace`。
- `.xlsx` 的 CSV 派生文件位于 `data/interim/raw_csv/`，并保留源工作簿、工作表名、行列数和 hash；公式使用工作簿缓存值。
- 确定性 QC 不评价建模、统计或论文质量。
- 本地 runner 不是安全沙箱，只运行可信代码。
- 历史 case 保持原样；FAST 只新增 `case.json` 和新目录约定。

## 测试

```powershell
python -m compileall -q harness
python -m unittest discover -s harness/tests -v
```
