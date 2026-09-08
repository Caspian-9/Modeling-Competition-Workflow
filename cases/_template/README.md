# FAST Case 模板说明

不要手工复制本目录。运行：

```powershell
python -m harness init <CASE_ID> --questions Q1 Q2 Q3 Q4
```

在桌面对话中，主 Agent 会询问 case ID 并请求附加题目 PDF 和数据文件；它会执行 `chat-intake` 将附件复制到 `raw/`。手动方式仍可将题目和数据放入 `cases/<CASE_ID>/raw/`，再运行：

```powershell
python -m harness intake <CASE_ID>
```

`.xlsx` 输入会自动将每个工作表导出为 `data/interim/raw_csv/` 下的 UTF-8 CSV，原工作簿保持只读。

主 Agent 持续维护 `workspace/`、`questions/<Q>/analysis.md` 和 `paper/manuscript.md`。实验通过 `experiment-create`、`run`、`qc` 和 `select` 管理；Judge、Librarian 和独立 Engineer 均按需调用。
