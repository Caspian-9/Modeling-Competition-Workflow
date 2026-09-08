# ModelViz 召回与 Nature-Figure 中文重绘

当论文图需要“候选图型召回 + 中文多面板重绘”时使用。ModelViz 只提供图型和构图线索，Nature-Figure 根据当前数据与论文结论原创绘图。

## 1. 定义 Figure Spec

绘图前写清：

- 一句话核心结论；
- 数据文件、字段、分析单位、样本范围和单位；
- 各面板分别提供什么证据；
- 允许的展示变换和禁止改变的统计口径；
- 中文标题、坐标轴、图例和注释；
- 最终尺寸、后端和 SVG/PDF/PNG/TIFF 需求；
- 最可能被评委质疑的误导风险。

Figure Spec 可用简洁 Markdown 或 JSON，保存在当前问 `figures/`。不需要 artifact ID、claim ID 或正式登记门禁。

## 2. ModelViz 只召回

使用已审查的本地 ModelViz：

```powershell
python .agents/skills/write-modeling-paper/scripts/modelviz_adapter.py `
  --recall-only `
  --modelviz-root <LOCAL_MODELVIZ_ROOT> `
  --output-root <FIGURE_WORK_DIR> `
  --question-id <Q> `
  --requirement-json <REQUIREMENT_JSON> `
  --top-k 8 `
  --report <RECALL_REPORT_JSON>
```

只采用 chart type、信息层级和面板组合线索。不复制、import 或执行候选模板代码。召回分数不是最终选择依据；数据结构、结论和可读性不匹配时直接拒绝。

## 3. Nature-Figure 重绘

调用 `nature-figure`：

1. 选择 Python 或 R 单一后端。
2. 根据 Figure Spec 和真实数据原创绘图代码。
3. 所有可见文字使用中文；通用缩写、变量和单位可保留。
4. 只做展示转换，不新增统计、重新拟合或改变筛选规则。
5. 保存可复现脚本、最终矢量图和必要位图预览。

## 4. 最终 QA

每次布局变化后重新检查：

- 数据与图形编码是否忠实；
- 各面板是否有独特且必要的职责；
- 标题、轴、单位、图例和注释是否完整；
- 中文字体是否嵌入且字号适合论文最终尺寸；
- 是否存在裁切、重叠、空白、错位、遮挡或近空图；
- 颜色是否可辨且灰度打印仍能区分；
- 图注是否说明对象、样本、统计量、误差表示和核心结论；
- 正文是否在图前后解释该图。

必须实际查看最终图像或渲染后的 PDF 页面，不能只依赖源码检查。将简短来源与 QA 记录保存在 `figures/figure_notes.md`，但论文正文只保留自然图注和结论。
