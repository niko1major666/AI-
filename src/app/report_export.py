"""差距报告导出：Markdown / Word（.docx）纯函数，供页面 download_button 与脚本复用。"""
from __future__ import annotations

import io
import re
from datetime import datetime

_ILLEGAL = re.compile(r'[\\/:*?"<>|\r\n\t]+')
_CN_FONT = "微软雅黑"


def safe_filename(company: str = "", title: str = "", ext: str = "md",
                  *, max_len: int = 60) -> str:
    """生成安全的下载文件名：去非法字符 + 截断 + 兜底名。"""
    raw = "_".join(x for x in [str(company or "").strip(), str(title or "").strip()] if x)
    name = _ILLEGAL.sub("_", raw)
    name = re.sub(r"\s+", "", name).strip("._")
    name = name[:max_len] or "gap_report"
    ext = str(ext or "md").lstrip(".")
    return f"{name}.{ext}"


def _missing_rows(report) -> list:
    return list(getattr(report, "missing", []) or [])


def report_markdown(report, *, company: str = "", job_title: str = "",
                    user_skills=(), generated_at: str = "",
                    learning_path=None) -> str:
    """GapReport -> Markdown 文本。

    learning_path: 可选 LearningPath（含 stages），用于附上规则版学习路径。
    """
    when = generated_at or datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = _missing_rows(report)
    lines = [
        "# 技能差距报告",
        "",
        f"- **目标岗位**：{company} · {job_title}".rstrip(" ·"),
        f"- **生成时间**：{when}",
        f"- **匹配度**：{getattr(report, 'match_score', 0)}%",
        f"- **命中 / 缺失**：{getattr(report, 'matched_total', 0)} 项 / "
        f"{getattr(report, 'missing_total', len(rows))} 项",
    ]
    if user_skills:
        lines.append("- **已具备技能**：" + "、".join(str(s) for s in user_skills))
    lines.append("")

    if not rows:
        lines += ["## 结论", "", "该岗位要求的技能已全部覆盖，暂无差距。", ""]
    else:
        p0 = [m for m in rows if getattr(m, "priority", "") == "P0"]
        p1 = [m for m in rows if getattr(m, "priority", "") == "P1"]
        p2 = [m for m in rows if getattr(m, "priority", "") == "P2"]
        lines += ["## 结论", "",
                  f"- P0（硬性门槛）缺失 **{len(p0)}** 项，P1（高频）**{len(p1)}** 项，"
                  f"P2（加分项）**{len(p2)}** 项。",
                  "- 建议先补 P0，再按 P1 顺序推进；每项都附了学习资源与最小项目建议。", ""]
        for label, group in (("P0 · 先学", p0), ("P1 · 进阶", p1), ("P2 · 可选", p2)):
            if not group:
                continue
            lines += [f"## {label}", ""]
            for m in group:
                tags = (f"重要度 {getattr(m, 'importance', '-')}/5 · "
                        f"难度 {getattr(m, 'difficulty', '-')}/4 · "
                        f"优先级分 {getattr(m, 'priority_score', '-')}")
                lines.append(f"### {getattr(m, 'name', m.skill_id)}")
                lines.append(f"- {tags}")
                why = str(getattr(m, "why", "") or "").strip()
                if why:
                    lines.append(f"- 判定依据：{why}")
                for r in (getattr(m, "resources", []) or [])[:3]:
                    title = (r or {}).get("title", "")
                    url = (r or {}).get("url", "")
                    lines.append(f"- 资源：[{title}]({url})" if url else f"- 资源：{title}")
                lines.append("")

        lines += ["## 缺失技能清单", "", "| 技能 | 优先级 | 重要度 | 难度 | 说明 |",
                  "|---|---|---|---|---|"]
        for m in rows:
            lines.append(f"| {getattr(m, 'name', m.skill_id)} | {getattr(m, 'priority', '')} | "
                         f"{getattr(m, 'importance', '')} | {getattr(m, 'difficulty', '')} | "
                         f"{str(getattr(m, 'why', '') or '').replace('|', '/')} |")
        lines.append("")

    if learning_path is not None and getattr(learning_path, "stages", None):
        from src.matcher.learning_path import format_path_markdown
        lines += ["## 学习路径（规则版）", "", format_path_markdown(learning_path), ""]
    return "\n".join(lines).strip() + "\n"


def _set_cn_font(run, *, size=None, bold: bool = False):
    from docx.oxml.ns import qn
    from docx.shared import Pt
    run.bold = bold
    run.font.name = _CN_FONT
    try:
        run._element.rPr.rFonts.set(qn("w:eastAsia"), _CN_FONT)
    except AttributeError:
        pass
    if size:
        run.font.size = Pt(size)


def _to_bytes(doc) -> bytes:
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def report_docx(report, *, company: str = "", job_title: str = "",
                user_skills=(), generated_at: str = "",
                learning_path=None) -> bytes:
    """GapReport -> .docx 字节流（python-docx 懒加载，未安装时抛 ImportError）。"""
    from docx import Document

    doc = Document()
    when = generated_at or datetime.now().strftime("%Y-%m-%d %H:%M")

    h = doc.add_heading(level=0)
    _set_cn_font(h.add_run("技能差距报告"), size=22, bold=True)

    info = [
        f"目标岗位：{company} · {job_title}".rstrip(" ·"),
        f"生成时间：{when}",
        f"匹配度：{getattr(report, 'match_score', 0)}%",
        f"命中 / 缺失：{getattr(report, 'matched_total', 0)} 项 / "
        f"{getattr(report, 'missing_total', len(_missing_rows(report)))} 项",
    ]
    if user_skills:
        info.append("已具备技能：" + "、".join(str(s) for s in user_skills))
    for line in info:
        p = doc.add_paragraph()
        _set_cn_font(p.add_run(line), size=10.5)

    rows = _missing_rows(report)
    if not rows:
        p = doc.add_paragraph()
        _set_cn_font(p.add_run("该岗位要求的技能已全部覆盖，暂无差距。"), size=11)
        return _to_bytes(doc)

    p0 = [m for m in rows if getattr(m, "priority", "") == "P0"]
    p1 = [m for m in rows if getattr(m, "priority", "") == "P1"]
    p2 = [m for m in rows if getattr(m, "priority", "") == "P2"]
    p = doc.add_paragraph()
    _set_cn_font(p.add_run(f"P0 {len(p0)} 项 · P1 {len(p1)} 项 · P2 {len(p2)} 项，建议先补 P0。"),
                 size=11, bold=True)

    for label, group in (("P0 · 先学", p0), ("P1 · 进阶", p1), ("P2 · 可选", p2)):
        if not group:
            continue
        hh = doc.add_heading(level=1)
        _set_cn_font(hh.add_run(label), size=15, bold=True)
        for m in group:
            p = doc.add_paragraph()
            _set_cn_font(p.add_run(str(getattr(m, "name", m.skill_id))), size=12, bold=True)
            _set_cn_font(p.add_run(f"　重要度 {getattr(m, 'importance', '-')}/5 · "
                                   f"难度 {getattr(m, 'difficulty', '-')}/4"), size=9.5)
            why = str(getattr(m, "why", "") or "").strip()
            if why:
                pp = doc.add_paragraph(style="List Bullet")
                _set_cn_font(pp.add_run(why), size=10)
            for r in (getattr(m, "resources", []) or [])[:3]:
                title = (r or {}).get("title", "")
                url = (r or {}).get("url", "")
                pp = doc.add_paragraph(style="List Bullet")
                _set_cn_font(pp.add_run(f"{title} {url}".strip()), size=10)

    hh = doc.add_heading(level=1)
    _set_cn_font(hh.add_run("缺失技能清单"), size=15, bold=True)
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    for cell, text in zip(table.rows[0].cells, ("技能", "优先级", "重要度", "难度")):
        cell.text = ""
        _set_cn_font(cell.paragraphs[0].add_run(text), size=10, bold=True)
    for m in rows:
        cells = table.add_row().cells
        for cell, text in zip(cells, (getattr(m, "name", m.skill_id),
                                      getattr(m, "priority", ""),
                                      str(getattr(m, "importance", "")),
                                      str(getattr(m, "difficulty", "")))):
            cell.text = ""
            _set_cn_font(cell.paragraphs[0].add_run(text), size=10)

    if learning_path is not None and getattr(learning_path, "stages", None):
        hh = doc.add_heading(level=1)
        _set_cn_font(hh.add_run("学习路径（规则版）"), size=15, bold=True)
        for st in learning_path.stages:
            p = doc.add_paragraph()
            _set_cn_font(p.add_run(f"{st.phase}（{st.hours} 学时 / 约 {st.weeks} 周）"),
                         size=11.5, bold=True)
            for i, step in enumerate(st.steps, 1):
                pp = doc.add_paragraph()
                _set_cn_font(pp.add_run(f"{i}. {step.name}（约 {step.hours} 学时）"), size=10.5)
                for r in (step.resources or [])[:2]:
                    if (r or {}).get("title"):
                        _set_cn_font(pp.add_run(f"　资源：{r.get('title')}"), size=9.5)
    return _to_bytes(doc)

