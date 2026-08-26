from __future__ import annotations

import hashlib
import re
import shutil
from collections import Counter
from pathlib import Path

import fitz
import yaml


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "官方优秀论文（21-25）"
KB = ROOT / "知识库"
CASES = KB / "06_优秀案例"
AUDIT = KB / "00_规范与索引"

TOPICS = {
    "2021": "生产企业原材料订购与运输",
    "2022": "古代玻璃成分数据分析与鉴别",
    "2023": "商超蔬菜销售、定价与补货",
    "2024": "农作物种植策略优化",
    "2025": "NIPT 时点优化与异常识别",
}

METHOD_PATTERNS = {
    "描述统计": r"描述统计|均值|标准差|箱线图",
    "相关分析": r"相关系数|相关性|Spearman|Pearson",
    "假设检验": r"显著性|假设检验|卡方检验|似然比检验|正态性检验",
    "回归": r"回归模型|线性回归|Logistic|逻辑回归",
    "混合效应模型": r"混合效应|LMM",
    "聚类": r"聚类|K-means|层次聚类",
    "主成分分析": r"主成分|PCA",
    "决策树": r"决策树",
    "随机森林": r"随机森林",
    "支持向量机": r"支持向量机|SVM",
    "梯度提升": r"XGBoost|LightGBM|梯度提升",
    "神经网络": r"神经网络|深度学习|LSTM|Transformer",
    "时间序列": r"时间序列|ARIMA|VAR\(",
    "贝叶斯模型": r"Bayesian|贝叶斯|MCMC",
    "线性/整数规划": r"线性规划|整数规划|0-1规划|LINGO",
    "多目标优化": r"多目标",
    "随机/鲁棒优化": r"随机优化|随机规划|鲁棒优化|CVaR|风险决策",
    "遗传/进化算法": r"遗传算法|差分进化|DEGA",
    "动态规划": r"动态规划",
    "蒙特卡洛": r"蒙特卡罗|Monte Carlo",
    "敏感性分析": r"敏感性分析|灵敏度分析",
    "交叉验证": r"交叉验证|交叉检验",
}

QUESTION_RE = re.compile(
    r"(?m)^(#{1,4})\s*(?:(?:\d+(?:\.\d+)*)\s*)?"
    r"(?:[四五六七八九十]+、)?(?:针对)?问题\s*([一二三四1234])(?:问|的)?[^\n]*$"
)
PAGE_MARK_RE = re.compile(r"<!--\s*(\d+)\s*-->")
REMOTE_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\((https?://[^)]+)\)")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def title_of(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if re.match(r"^#{1,2}\s+", line):
            title = re.sub(r"^#{1,2}\s+", "", line).strip()
            title = re.sub(r"摘要$", "", title).strip()
            if title and not re.match(r"^[一二三四五六七八九十]+、", title):
                return title
    return fallback


def page_mark_stats(text: str) -> tuple[list[int], int]:
    marks = [int(x) for x in PAGE_MARK_RE.findall(text)]
    counts = Counter(marks)
    return marks, sum(v - 1 for v in counts.values() if v > 1)


def split_by_page_marks(text: str) -> list[str]:
    pieces: list[str] = []
    start = 0
    for match in PAGE_MARK_RE.finditer(text):
        pieces.append(text[start : match.start()])
        start = match.end()
    pieces.append(text[start:])
    return pieces


def clean_c25_01(text: str) -> tuple[str, list[str]]:
    """Keep NIPT blocks from an interleaved OCR container."""
    keep_terms = re.compile(
        r"NIPT|染色体|孕妇|孕周|BMI|胎儿|女胎|男胎|游离DNA|Z值|GC含量|Chr[XY]|混合效应",
        re.I,
    )
    reject_terms = re.compile(
        r"供货商|供应商|订货|供货|转运商|原材料|库存|产能|运输损耗|生产企业|402家|24周",
        re.I,
    )
    kept: list[str] = []
    removed: list[str] = []
    last_choice = True
    for block in split_by_page_marks(text):
        pos = len(keep_terms.findall(block))
        neg = len(reject_terms.findall(block))
        # Very short continuation blocks inherit their neighbor stream only if no signal exists.
        choice = pos >= neg if pos or neg else last_choice
        if choice:
            kept.append(block)
        else:
            removed.append(block)
        last_choice = choice
    selected = "\n\n".join(kept)
    # A few OCR pages contain two columns from different papers in one Markdown block.
    # Remove only paragraphs/rows with a strong supply-chain signal after page-level selection.
    refined: list[str] = []
    for paragraph in re.split(r"\n\s*\n", selected):
        pos = len(keep_terms.findall(paragraph))
        neg = len(reject_terms.findall(paragraph))
        if neg >= 2 and neg > pos:
            removed.append(paragraph)
            continue
        if neg and pos:
            sentences = re.split(r"(?<=[。！？；])", paragraph)
            good_sentences: list[str] = []
            for sentence in sentences:
                spos = len(keep_terms.findall(sentence))
                sneg = len(reject_terms.findall(sentence))
                if sneg >= 2 and sneg > spos:
                    removed.append(sentence)
                else:
                    good_sentences.append(sentence)
            paragraph = "".join(good_sentences)
        if paragraph.strip():
            refined.append(paragraph)
    selected = "\n\n".join(refined)
    # Known mixed-column fragment with no strong topic keywords in its heading.
    mixed_section = re.compile(
        r"(?ms)^#{2,3}\s*5\.3\s*基于TOPSIS的多指标评价模型的求解.*?(?=^#{1,3}\s*4\.5\s*模型检验)"
    )
    match = mixed_section.search(selected)
    if match:
        removed.append(match.group(0))
        selected = selected[: match.start()] + selected[match.end() :]
    residual = re.compile(
        r"(?ms)\n就越大。相反，某个指标的信息熵.*?TOPSIS\(Technique for Order Preference.*?作为评价优劣的依据。\s*"
    )
    match = residual.search(selected)
    if match:
        removed.append(match.group(0))
        selected = selected[: match.start()] + "\n" + selected[match.end() :]
    selected = re.sub(
        r"(?m)^#\s*基于混合效应模型的NIPT时点优化与胎儿异常判定摘要\s*$",
        "# 基于混合效应模型的 NIPT 时点优化与胎儿异常判定\n\n## 摘要",
        selected,
        count=1,
    )
    return selected, removed


def clean_c24_02_front(text: str) -> tuple[str, list[str]]:
    """Conservative cleanup: remove only the clearly foreign second abstract/front matter."""
    start = text.find("## 基于优化算法的农作物最优种植模型")
    end = text.find("## 一、引言")
    removed: list[str] = []
    if start != -1 and end != -1 and start < end:
        removed.append(text[start:end])
        text = text[:start] + text[end:]
    text = re.sub(r"(?m)^中国大学生在线\s*$", "", text)
    text = re.sub(r"(?m)^dxs\.moe\.gov\.cn\s*$", "", text)
    return text, removed


def normalize(text: str, image_manifest: list[dict]) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = PAGE_MARK_RE.sub("", text)
    # Remove long OCR descriptions embedded as HTML comments while retaining ordinary prose.
    text = re.sub(r"<!--(?:(?!-->).){25,}-->", "", text, flags=re.S)

    def replace_image(match: re.Match[str]) -> str:
        url = match.group(2)
        asset_id = "remote_" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
        image_manifest.append({"asset_id": asset_id, "url": url, "status": "pending_localization"})
        return f"[图像资产待本地化：{asset_id}]"

    text = REMOTE_IMAGE_RE.sub(replace_image, text)
    text = re.sub(r"(?m)^[ \t]+$", "", text)
    text = re.sub(r"中国\s*dxs\.moe\.gov\.cn", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def extract_methods(text: str) -> list[str]:
    return [name for name, pattern in METHOD_PATTERNS.items() if re.search(pattern, text, re.I)]


def question_sections(text: str) -> list[tuple[str, str]]:
    matches = list(QUESTION_RE.finditer(text))
    result: list[tuple[str, str]] = []
    seen: Counter[str] = Counter()
    cn_to_num = {"一": "1", "二": "2", "三": "3", "四": "4"}
    for i, match in enumerate(matches):
        q = cn_to_num.get(match.group(2), match.group(2))
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[match.start() : end].strip()
        if len(body) < 180:
            continue
        seen[q] += 1
        suffix = "" if seen[q] == 1 else f"_part{seen[q]}"
        result.append((f"Q{q}{suffix}", body))
    # Keep the most substantive section for each question. Analysis-only headings often
    # precede the real model section and otherwise create noisy duplicates.
    best: dict[str, tuple[str, str]] = {}
    for qid, body in result:
        base = qid.split("_")[0]
        current = best.get(base)
        if current is None or len(body) > len(current[1]):
            best[base] = (base, body)
    return [best[key] for key in sorted(best, key=lambda x: int(x[1:]))]


def abstract_excerpt(text: str, max_chars: int = 900) -> str:
    start_match = re.search(r"(?m)^#{1,3}\s*摘要\s*$", text)
    if start_match:
        tail = text[start_match.end() :]
    else:
        tail = text
    next_heading = re.search(r"(?m)^#{1,3}\s+", tail)
    excerpt = tail[: next_heading.start() if next_heading else max_chars]
    excerpt = re.sub(r"\s+", " ", excerpt).strip()
    return excerpt[:max_chars]


def innovation_excerpt(text: str) -> list[str]:
    sentences = re.split(r"(?<=[。！？；])", re.sub(r"\s+", " ", text))
    hits = [s.strip() for s in sentences if re.search(r"创新|改进|提出|引入|融合|构建", s)]
    unique: list[str] = []
    for item in hits:
        if 25 <= len(item) <= 420 and item not in unique:
            unique.append(item)
    return unique[:12]


def extract_pdf_images(pdf_path: Path, assets_dir: Path) -> list[dict]:
    records: list[dict] = []
    if not pdf_path.exists():
        return records
    image_dir = assets_dir / "pdf_images"
    image_dir.mkdir(parents=True, exist_ok=True)
    seen: set[int] = set()
    with fitz.open(pdf_path) as doc:
        for page_index, page in enumerate(doc):
            for item in page.get_images(full=True):
                xref = item[0]
                if xref in seen:
                    continue
                seen.add(xref)
                data = doc.extract_image(xref)
                width, height = data.get("width", 0), data.get("height", 0)
                # Tiny masks, bullets and decorative fragments have little retrieval value.
                if width < 120 or height < 80:
                    continue
                ext = data.get("ext", "bin")
                name = f"xref_{xref}.{ext}"
                (image_dir / name).write_bytes(data["image"])
                records.append(
                    {
                        "file": f"pdf_images/{name}",
                        "xref": xref,
                        "first_seen_page": page_index + 1,
                        "width": width,
                        "height": height,
                        "mapping_to_markdown": "unresolved",
                    }
                )
    return records


def critique(text: str, methods: list[str], issues: list[str]) -> str:
    checks = {
        "基线对比": bool(re.search(r"基线|对比模型|传统模型|相比", text)),
        "统计检验": bool(re.search(r"显著性|p值|p-value|置信区间|假设检验|似然比检验", text, re.I)),
        "交叉验证": bool(re.search(r"交叉验证|交叉检验", text)),
        "敏感性/稳健性": bool(re.search(r"敏感性|灵敏度|稳健|鲁棒", text)),
        "误差或不确定性": bool(re.search(r"误差|不确定性|置信区间|风险", text)),
        "可复现线索": bool(re.search(r"Python|MATLAB|R语言|LINGO|代码|附录", text, re.I)),
    }
    lines = ["# 评委批判性审查", "", "## 自动证据检查", ""]
    lines += [f"- {'已检出' if value else '未明确检出'}：{name}" for name, value in checks.items()]
    lines += ["", "## 方法覆盖", "", ", ".join(methods) if methods else "未自动识别出方法名。"]
    lines += ["", "## 数据治理问题", ""]
    lines += [f"- {x}" for x in issues] if issues else ["- 未发现阻断性文档污染；仍需人工核对公式、表格和结论数值。"]
    lines += [
        "",
        "## 使用约束",
        "",
        "- 本文是高价值案例，不是绝对正确答案；模型假设必须结合新题数据重新验证。",
        "- 检索到模型名称时，应同时检索其适用条件、诊断方法和失败模式。",
        "- 论文中的数值结论不得迁移到新题；只能迁移分析结构和验证思想。",
        "- 若缺少基线、数据划分或复现信息，Agent 必须补做，不得因来源为优秀论文而跳过。",
    ]
    return "\n".join(lines) + "\n"


def ensure_skeleton() -> None:
    for name in [
        "00_规范与索引",
        "01_共享基础",
        "02_建模手",
        "03_工程师",
        "04_论文手",
        "05_评委",
        "06_优秀案例",
        "07_测试集",
    ]:
        (KB / name).mkdir(parents=True, exist_ok=True)


def process_one(md_path: Path) -> dict:
    year = md_path.parent.name
    source_id = md_path.stem
    pdf_path = md_path.with_suffix(".pdf")
    raw = md_path.read_text(encoding="utf-8")
    marks, duplicate_marks = page_mark_stats(raw)
    remote_count = len(REMOTE_IMAGE_RE.findall(raw))
    issues: list[str] = []
    removed: list[str] = []

    if source_id == "C25-01":
        raw, removed = clean_c25_01(raw)
        issues.append("源容器存在 NIPT 与供应链串文；清洗正文使用主题分类剔除了供应链块。")
        issues.append("主题分类边界仍需结合原版单篇 PDF 人工抽查。")
    elif source_id == "C24-02":
        raw, removed = clean_c24_02_front(raw)
        issues.append("按用户确认仅移除了开头可明确识别的第二篇摘要/站点水印。")
        if duplicate_marks:
            issues.append("全文仍存在重复页码序列和章节并行迹象，保守保留并标记待人工复核。")

    image_manifest: list[dict] = []
    cleaned = normalize(raw, image_manifest)
    title = title_of(cleaned, source_id)
    methods = extract_methods(cleaned)
    questions = question_sections(cleaned)
    headings = re.findall(r"(?m)^#{1,3}\s+(.+)$", cleaned)
    pdf_pages = None
    if pdf_path.exists():
        with fitz.open(pdf_path) as doc:
            pdf_pages = len(doc)

    case_dir = CASES / f"{year}_{source_id}"
    if case_dir.exists():
        shutil.rmtree(case_dir)
    (case_dir / "questions").mkdir(parents=True)
    (case_dir / "assets").mkdir(parents=True)

    (case_dir / "01_清洗正文.md").write_text(cleaned, encoding="utf-8")
    if removed:
        (case_dir / "audit_removed_fragments.md").write_text(
            "# 自动排除片段（仅供审计，不应导入知识库）\n\n"
            + "\n\n---\n\n".join(x.strip() for x in removed if x.strip()),
            encoding="utf-8",
        )
    for qid, body in questions:
        (case_dir / "questions" / f"{qid}_方法与结果.md").write_text(
            f"---\nsource_id: {source_id}\nyear: {year}\nquestion_id: {qid}\n---\n\n{body}\n",
            encoding="utf-8",
        )

    (case_dir / "assets" / "remote_images.yaml").write_text(
        yaml.safe_dump(image_manifest, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    pdf_images = extract_pdf_images(pdf_path, case_dir / "assets")
    (case_dir / "assets" / "pdf_images.yaml").write_text(
        yaml.safe_dump(pdf_images, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    quality_score = max(
        0.25,
        min(0.95, 0.92 - 0.08 * bool(duplicate_marks) - 0.06 * bool(remote_count) - 0.10 * (source_id == "C25-01")),
    )
    metadata = {
        "source_id": source_id,
        "year": int(year),
        "problem": "C",
        "title": title,
        "topic": TOPICS[year],
        "methods": methods,
        "roles": ["modeler", "engineer", "writer", "judge"],
        "evidence_level": "official_excellent_paper",
        "verified": False,
        "quality_score": round(quality_score, 2),
        "source_markdown": str(md_path.relative_to(ROOT)).replace("\\", "/"),
        "source_pdf": str(pdf_path.relative_to(ROOT)).replace("\\", "/") if pdf_path.exists() else None,
        "source_markdown_sha256": sha256(md_path),
        "source_pdf_sha256": sha256(pdf_path) if pdf_path.exists() else None,
        "pdf_pages": pdf_pages,
        "question_sections": [qid for qid, _ in questions],
        "remote_image_references": len(image_manifest),
        "local_pdf_images": len(pdf_images),
        "requires_human_review": bool(issues or duplicate_marks or remote_count),
    }
    (case_dir / "metadata.yaml").write_text(
        yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    card = [
        f"# {source_id} 论文卡片",
        "",
        f"- 标题：{title}",
        f"- 年份与题号：{year} 国赛 C 题",
        f"- 主题：{TOPICS[year]}",
        f"- PDF 页数：{pdf_pages if pdf_pages is not None else '缺失'}",
        f"- 自动识别方法：{', '.join(methods) if methods else '待补充'}",
        f"- 分小问文档：{', '.join(q for q, _ in questions) if questions else '未可靠识别'}",
        f"- 当前质量分：{quality_score:.2f}",
        f"- 人工复核：{'需要' if metadata['requires_human_review'] else '建议抽查'}",
        "",
        "## 摘要摘录",
        "",
        abstract_excerpt(cleaned),
        "",
        "## 主要章节",
        "",
    ]
    card += [f"- {h}" for h in headings[:35]]
    (case_dir / "00_论文卡片.md").write_text("\n".join(card) + "\n", encoding="utf-8")
    mapping = [
        "# 题目与小问映射",
        "",
        "下列条目由章节标题自动识别，入库前应抽查是否覆盖全部题目要求。",
        "",
        "| 小问 | 文档 | 自动识别方法 |",
        "|---|---|---|",
    ]
    for qid, _ in questions:
        mapping.append(f"| {qid} | `questions/{qid}_方法与结果.md` | {', '.join(methods) if methods else '待人工标注'} |")
    if not questions:
        mapping.append("| 待人工拆分 | 暂未可靠识别 | 待人工标注 |")
    (case_dir / "02_题目与小问映射.md").write_text("\n".join(mapping) + "\n", encoding="utf-8")

    innovations = [
        "# 创新点候选",
        "",
        "以下内容为自动抽取的候选主张，不代表评委已认可。每项需通过基线、消融实验或理论依据验证。",
        "",
    ]
    extracted = innovation_excerpt(cleaned)
    innovations += [f"- {x}" for x in extracted] if extracted else ["- 未可靠抽取；需人工结合模型与基线补充。"]
    (case_dir / "08_创新点.md").write_text("\n".join(innovations) + "\n", encoding="utf-8")
    (case_dir / "09_评委批判性审查.md").write_text(critique(cleaned, methods, issues), encoding="utf-8")

    return {
        "source_id": source_id,
        "year": year,
        "title": title,
        "characters_raw": len(md_path.read_text(encoding="utf-8")),
        "characters_clean": len(cleaned),
        "pdf_pages": pdf_pages,
        "page_marks": len(marks),
        "duplicate_page_marks": duplicate_marks,
        "remote_images": remote_count,
        "question_docs": len(questions),
        "local_pdf_images": len(pdf_images),
        "quality_score": round(quality_score, 2),
        "issues": issues,
    }


def write_standards() -> None:
    (AUDIT / "元数据规范.md").write_text(
        """# 优秀案例元数据规范

必填字段包括 `source_id`、`year`、`problem`、`title`、`topic`、`methods`、`roles`、`evidence_level`、`verified`、`quality_score`、来源路径和 SHA-256。

- `verified: false` 表示尚未逐公式、逐数值与 PDF 人工核验。
- `quality_score` 是文档可检索质量，不代表论文竞赛水平。
- `requires_human_review` 为真时，入库前应查看论文卡片和评委审查。
- 所有清洗文档必须可追溯到只读原始文件，禁止覆盖原文。
""",
        encoding="utf-8",
    )
    (AUDIT / "文档质量检查规则.md").write_text(
        """# 文档质量检查规则

1. 标题和年份题号一致。
2. 页码序列、章节编号和小问顺序不存在无法解释的重复。
3. 不含其他年份或主题的串文。
4. 远程图片必须进入资产清单；本地化前不得声称图片已永久保存。
5. 公式、表头和图注应与上下文相连。
6. OCR 错别字、站点水印和分页注释不进入检索正文。
7. 自动清洗无法确定边界时，保守保留并标记人工复核。
8. 优秀论文仅作为案例证据，不能替代模型假设和统计诊断。
""",
        encoding="utf-8",
    )
    (AUDIT / "Dify导入清单.md").write_text(
        """# Dify 导入清单（第一阶段）

## 建议导入

- `06_优秀案例/*/00_论文卡片.md`
- `06_优秀案例/*/questions/*.md`
- `06_优秀案例/*/08_创新点.md`（仅作为候选创新，提示词中必须要求验证）
- `06_优秀案例/*/09_评委批判性审查.md`

若需要更完整上下文，可把 `01_清洗正文.md` 放入独立的“优秀论文全文库”，不要与短方法卡使用相同召回权重。

## 不应导入

- `audit_removed_fragments.md`
- `assets/*.yaml`
- `00_规范与索引/第一阶段语料质量报告.md`
- 原始未清洗 Markdown
- `_audit_previews/`

## 检索建议

优先按 `year`、`question_id`、`topic`、`methods` 和 `roles` 过滤，再进行混合检索和重排序。优秀案例只能作为类比证据，不能把案例数值迁移到当前题目。
""",
        encoding="utf-8",
    )


def write_report(rows: list[dict]) -> None:
    header = [
        "# 第一阶段语料质量报告",
        "",
        "生成方式：`python 知识库/scripts/build_phase1.py`",
        "",
        "| 来源 | 标题 | PDF页数 | 原始字符 | 清洗字符 | 重复页码标记 | 远程图片 | PDF本地图片 | 小问文档 | 质量分 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        header.append(
            f"| {r['source_id']} | {r['title']} | {r['pdf_pages']} | {r['characters_raw']} | "
            f"{r['characters_clean']} | {r['duplicate_page_marks']} | {r['remote_images']} | {r['local_pdf_images']} | "
            f"{r['question_docs']} | {r['quality_score']:.2f} |"
        )
    header += ["", "## 需要人工复核", ""]
    for r in rows:
        notes = list(r["issues"])
        if r["duplicate_page_marks"] and not notes:
            notes.append("存在重复页码标记，可能来自 OCR 页序或合并容器。")
        if r["remote_images"]:
            notes.append(f"有 {r['remote_images']} 张远程 OCR 图片尚待本地化。")
        if notes:
            header.append(f"### {r['source_id']}")
            header.append("")
            header += [f"- {x}" for x in notes]
            header.append("")
    (AUDIT / "第一阶段语料质量报告.md").write_text("\n".join(header), encoding="utf-8")


def main() -> None:
    ensure_skeleton()
    write_standards()
    rows = [process_one(path) for path in sorted(SOURCE.rglob("*.md"))]
    write_report(rows)
    print(f"processed={len(rows)}")
    print(f"case_dirs={len(list(CASES.glob('*_C*')))}")
    print(f"question_docs={sum(r['question_docs'] for r in rows)}")
    print(f"remote_images_pending={sum(r['remote_images'] for r in rows)}")
    print(f"local_pdf_images={sum(r['local_pdf_images'] for r in rows)}")


if __name__ == "__main__":
    main()
