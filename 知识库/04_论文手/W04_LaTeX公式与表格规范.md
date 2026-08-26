---
card_id: W04
card_type: writing
roles:
- writer
- judge
verified: true
---

# LaTeX 公式与表格规范

行内公式使用 `$...$`，重要公式使用带编号环境。向量、矩阵、集合和随机变量字体统一；首次出现的每个符号必须定义。长公式按等号或运算符对齐，不使用截图公式。

表格优先 `booktabs`，避免密集竖线；跨页表使用 `longtable`。所有图表使用 `\label` 和 `\ref` 交叉引用。编译前检查未定义引用、溢出框、缺失字体及图片路径。
