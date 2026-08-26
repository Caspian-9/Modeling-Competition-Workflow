---
card_id: WR05
card_type: external_writer_integration
roles:
- writer
- judge
verified: true
source_license: MIT
---

# 外部模板 Dify 导入边界

## 主知识库导入

- 通用写作规范，但排除AI协作Prompt模板。
- 各题型的“问题分析要点”和“建模要点”。
- LaTeX排版规则和结构化撰写速查。
- 本目录WR01–WR05，用于提供来源和冲突约束。

## 不导入或另建低优先级库

- `AI使用规范.txt`：合规主张未核验。
- `摘要范例.md`、`专用话术.md`：易诱发套话和案例内容迁移。
- `.tex`：作为文件资产使用，不做普通向量检索。
- README、CONTRIBUTING和LICENSE：保留在源仓库，不作为写作知识召回。

检索到外部模板建议后，论文手必须同时检索本知识库的写作规范和评委规则；出现冲突时不得自行选择宽松版本。
