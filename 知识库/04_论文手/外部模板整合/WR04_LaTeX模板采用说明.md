---
card_id: WR04
card_type: external_writer_integration
roles:
- writer
- judge
verified: true
source_license: MIT
---

# LaTeX 模板采用说明

模板基于 `ctexart`、Fandol字体和XeLaTeX，适合作为论文工程起点。使用时先复制到运行时项目的 `paper/` 目录，再按当年官方模板调整页面、标题、编号和匿名要求；不要直接在知识库源文件上写比赛论文。

采用前检查：TeX发行版和宏包；全部 `【替换】` 占位符；示例文献与示例数字；页眉、页码、封面、承诺书和AI声明是否符合当年官方要求。推荐使用 `latexmk -xelatex`，将编译警告、未定义引用和溢出版面纳入终审。
