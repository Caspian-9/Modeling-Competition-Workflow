from __future__ import annotations

import hashlib
import re
from pathlib import Path

import fitz
import yaml


ROOT = Path(__file__).resolve().parents[2]
KB = ROOT / "知识库"
PDF = KB / "00_规范与索引" / "全国大学生数学建模竞赛论文格式规范.pdf"
OUT = KB / "04_论文手" / "官方格式规范"


def frontmatter(card_id: str, title: str) -> str:
    meta = {
        "card_id": card_id,
        "card_type": "official_format_rule",
        "title": title,
        "authority_level": "A_official",
        "roles": ["writer", "judge"],
        "verified": True,
        "source": "00_规范与索引/全国大学生数学建模竞赛论文格式规范.pdf",
        "edition": "2026年修订稿",
    }
    return "---\n" + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip() + "\n---\n\n"


def main() -> None:
    if not PDF.exists():
        raise FileNotFoundError(PDF)
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("OF*.md"):
        old.unlink()

    with fitz.open(PDF) as doc:
        pages = [page.get_text().strip() for page in doc]
        metadata = doc.metadata
    digest = hashlib.sha256(PDF.read_bytes()).hexdigest()

    source = frontmatter("OF00", "官方格式规范来源记录") + f"""# 官方格式规范来源记录

- 文件：`知识库/00_规范与索引/全国大学生数学建模竞赛论文格式规范.pdf`
- 标题：全国大学生数学建模竞赛论文格式规范
- 版本：2026年修订稿
- 页数：{len(pages)}
- PDF创建日期：{metadata.get('creationDate', '')}
- SHA-256：`{digest}`
- 权威等级：A级；格式冲突时优先于知识库规则、优秀论文和外部模板。

引用官方要求时必须注明条款号和PDF页码。本文档是检索入口，原始PDF是最终核对依据。
"""
    (OUT / "OF00_官方格式规范来源记录.md").write_text(source, encoding="utf-8")

    extracted = frontmatter("OF01", "官方格式规范逐页文本") + "# 官方格式规范逐页文本\n\n"
    for number, text in enumerate(pages, 1):
        extracted += f"## PDF 第{number}页\n\n{text}\n\n"
    (OUT / "OF01_官方格式规范逐页文本.md").write_text(extracted, encoding="utf-8")

    rules = frontmatter("OF02", "官方论文格式条款卡") + """# 官方论文格式条款卡

## 纸质版

| 条款 | 强制要求 | 来源 |
|---|---|---|
| 第一条 | 白色A4纸；单/双面均可；四边页边距至少2.5厘米；左侧装订 | PDF第1页 |
| 第二条 | 第一页承诺书，第二页编号专用页 | PDF第1页 |
| 第三条 | 第三页摘要专用页；摘要含标题和关键词，原则上不超过一页，无需英文；从该页以阿拉伯数字1连续编页码，页码在页脚中部 | PDF第1页 |
| 第四条 | 第四页起正文；不要目录；正文不超过30页；正文后附录页数不限并与正文装订 | PDF第1页 |
| 第五条 | 附录列支撑材料文件清单，并包含全部完整可运行源程序/交互命令；无程序时必须明确说明 | PDF第1页 |
| 第六条 | 摘要、正文和附录不得出现参赛者身份、学校或赛区信息 | PDF第1页 |
| 第七条 | 所有他人或公开资料成果必须列参考文献并在正文标注 | PDF第1页 |
| 第八条 | 字号、字体、行距、颜色不作统一要求；赛区可在不冲突前提下另作要求 | PDF第1页 |

## 电子版与支撑材料

| 条款 | 强制要求 | 来源 |
|---|---|---|
| 第九条 | 按报名和参赛须知提交论文、支撑材料两个电子文件 | PDF第1页 |
| 第十条 | 电子论文与纸质版内容及格式（含附录）一致；单独PDF或Word，建议PDF；不超过20MB；不压缩；不含承诺书和编号页；第一页必须为摘要页 | PDF第1页 |
| 第十一条 | 支撑材料至少含全部可运行程序、自主查阅数据、较大中间图表；RAR/ZIP且不超过20MB；文件清单进入附录；无支撑材料时需声明；不得含身份、学校、赛区信息 | PDF第2页 |
| 第十二条 | 自发布之日起试行；与旧规范冲突时以本规范为准；违规可能取消评奖资格 | PDF第2页 |
| 第十三条 | 解释权归全国大学生数学建模竞赛组委会 | PDF第2页 |

“可能取消评奖资格”只适用于官方条款原文涉及的情形，Agent不得自行扩展处罚范围。
"""
    (OUT / "OF02_官方论文格式条款卡.md").write_text(rules, encoding="utf-8")

    checklist = frontmatter("OF03", "官方格式提交检查表") + """# 官方格式提交检查表

## 纸质论文

- [ ] A4白纸，四边页边距均不少于2.5厘米，左侧装订。
- [ ] 第1页承诺书，第2页编号专用页，第3页摘要专用页。
- [ ] 摘要含标题和关键词，原则上不超过1页，无英文翻译。
- [ ] 摘要页页码为1，页脚居中；后续连续编号。
- [ ] 第4页开始正文且没有目录；正文不超过30页。
- [ ] 附录紧随正文并打印装订；附录包含支撑材料清单和完整可运行代码。
- [ ] 摘要、正文、附录无姓名、学校、赛区等身份信息。
- [ ] 所有外部成果在正文引用并列入参考文献。

## 电子论文

- [ ] 与纸质论文的摘要、正文和附录完全一致。
- [ ] 单一PDF或Word文件，建议PDF，大小不超过20MB且不压缩。
- [ ] 不含承诺书和编号专用页；电子版第一页是摘要专用页。

## 支撑材料

- [ ] 单独RAR或ZIP，不超过20MB。
- [ ] 含所有可运行源程序、自主查阅数据和必要中间结果。
- [ ] 支撑材料文件列表与论文附录一致。
- [ ] 支撑材料与论文方法、结果一致，且无身份、学校、赛区信息。
- [ ] 若没有程序或支撑材料，附录使用官方要求的明确说明。

任一未通过项都必须标明证据路径和责任人；涉及页数、大小、匿名、文件一致性或程序可运行性时不得仅口头确认。
"""
    (OUT / "OF03_官方格式提交检查表.md").write_text(checklist, encoding="utf-8")

    conflicts = frontmatter("OF04", "官方规范与外部模板冲突覆盖表") + """# 官方规范与外部模板冲突覆盖表

| 事项 | 官方2026修订稿 | 外部模板常见表述 | 处理决定 |
|---|---|---|---|
| 摘要长度 | 原则上不超过1页 | 600–900字、固定六段 | 一页是官方要求；字数和六段法仅为建议 |
| 正文长度 | 不超过30页 | 以20页或特定字数分配 | 30页为上限；其他为写作建议 |
| 目录 | 明确“不要目录” | 模板中目录为可选 | 国赛提交时不得启用目录 |
| 字体字号行距颜色 | 不统一要求，可有赛区附加要求 | Fandol、Times、1.5倍行距等 | 模板设置可用但不是全国统一硬性标准 |
| 章节顺序 | 本规范未规定固定八段顺序 | 声称顺序不可调整 | 只能作为组织建议，不能作为官方扣分项 |
| 标题编号 | 本规范未规定必须中文数字 | 声称中文数字是硬性要求 | 非本PDF官方要求；以赛区/当年其他官方文件为准 |
| 摘要数字加粗 | 本规范未规定 | 每问必须有加粗数字 | 有具体结果是良好写作；加粗不是本PDF强制要求 |
| 图题、表题和三线表 | 本规范未规定 | 图下表上、必须三线表 | 作为学术排版建议，不冒充官方硬性条款 |
| AI使用声明 | 本规范未涉及 | 声称固定位置及AIDC阈值 | 本PDF不能证实；必须另查官方AI专项通知 |
| 电子论文首页 | 必须是摘要页，不含承诺书/编号页 | 模板可能只含摘要正文 | 按官方条款生成电子提交版 |
| 源程序与支撑材料 | 完整、可运行、与论文一致 | 一般建议附代码 | 提升为官方强制检查项 |

外部模板仍可用于提高表达和排版质量，但不得覆盖官方条款，也不得把经验建议改写成取消资格依据。
"""
    (OUT / "OF04_官方规范与外部模板冲突覆盖表.md").write_text(conflicts, encoding="utf-8")

    print(f"official_cards={len(list(OUT.glob('OF*.md')))}")
    print(f"pdf_pages={len(pages)}")
    print(f"sha256={digest}")


if __name__ == "__main__":
    main()
