# Dify 分库与检索配置

不要把全部文件放进同一个数据集。规则库需要精确、低 top-k 检索，案例库需要混合检索与重排序；全文案例建议另建低优先级数据集。

| 数据集 | 使用角色 | 建议检索 | top-k |
|---|---|---|---:|
| 共享统计与验证规范 | modeler, engineer, judge | hybrid | 5 |
| 建模方法卡 | modeler, engineer, judge | hybrid_with_rerank | 7 |
| 工程故障与复现 | engineer, judge | hybrid | 5 |
| 论文写作规范 | writer, judge | keyword_first | 5 |
| 评委规则与评分 | judge | keyword_first | 6 |
| 优秀案例结构化证据 | modeler, engineer, writer, judge | hybrid_with_rerank | 6 |

## 关键约束

- 评委规则库始终优先于案例做法；案例与规则冲突时按规则返工。
- 建模手先检索模型选择图谱，再检索最多两到三张候选模型卡和相应案例。
- 论文手只能引用运行时成果仓库中的已审核数值；知识库案例数字不得迁移到当前题目。
- `plan_state.json`、代码、实验结果和论文草稿不进入这些静态数据集。
- Dify 实际 chunk 建议以 Markdown 标题为边界，保留 YAML 元数据；导入后用测试集调阈值而非只调 top-k。
