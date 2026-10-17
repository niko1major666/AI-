"""Streamlit 前端：技能图谱 / 简历匹配 / 差距报告。"""
from __future__ import annotations

import difflib
import json
import re
from collections import Counter
from pathlib import Path

import streamlit as st

from src.data.translate import translate_title as _translate_title

ROOT = Path(__file__).resolve().parents[2]

st.set_page_config(page_title="AI 岗位技能差距分析", layout="wide")

_PRIORITY_COLOR = {"P0": "#e74c3c", "P1": "#e67e22", "P2": "#3498db"}


def _priority_badge(p: str) -> str:
    color = _PRIORITY_COLOR.get(p, "#888888")
    return (f'<span style="background:{color};color:white;padding:3px 10px;'
            f'border-radius:4px;font-size:0.85em;font-weight:600;">{p}</span>')


def _stars(n: int, total: int) -> str:
    """把数值渲染成 ★★★☆☆ 形式的星级。"""
    n = max(0, min(int(n), total))
    return "★" * n + "☆" * (total - n)


_PRIO_BG = {"P0": "#fdecea", "P1": "#fff4e5", "P2": "#eef4fb"}
_PRIO_ACCENT = {"P0": "#e74c3c", "P1": "#e67e22", "P2": "#3498db"}


def _gap_card(m) -> str:
    """单个缺失技能的卡片 HTML（按 P 级着色，内容分行更分明）。"""
    bg = _PRIO_BG.get(m.priority, "#f6f8fa")
    accent = _PRIO_ACCENT.get(m.priority, "#888888")
    badge = _priority_badge(m.priority)
    return (
        f'<div style="background:{bg}; border-left:4px solid {accent}; border-radius:8px;'
        f'padding:10px 14px; margin:8px 0;">'
        f'<div style="font-weight:600; color:#1f3a5f; font-size:1.02em;">{m.name} {badge}</div>'
        f'<div style="margin-top:6px; color:#444; font-size:0.92em;">'
        f'<span>重要度&nbsp;<b style="color:{accent};">{_stars(m.importance, 5)}</b></span>'
        f'<span style="margin:0 10px; color:#ccc;">|</span>'
        f'<span>学习难度&nbsp;<b>{_stars(m.difficulty, 4)}</b></span>'
        f'</div>'
        f'<div style="margin-top:5px; color:#777; font-size:0.88em;">{m.why}</div>'
        f'</div>'
    )


def _inject_css():
    st.markdown("""
    <style>
    .block-container {padding-top: 2rem; padding-bottom: 2rem; max-width: 1200px;}
    h1, h2, h3, h4 {color: #1f3a5f;}
    [data-testid="stMetricValue"] {color: #1f6feb; font-weight: 700;}
    .stButton > button {background-color: #1f6feb; color: white; border-radius: 8px; border: none;}
    .stButton > button:hover {background-color: #1756c0;}
    </style>
    """, unsafe_allow_html=True)


@st.cache_resource
def load_core():
    import yaml
    from src.extractor.rule_baseline import RuleBaselineExtractor
    from src.matcher.gap_analyzer import SkillGapAnalyzer
    from src.matcher.tfidf_matcher import TfidfMatcher
    from src.skillkb.loader import Taxonomy

    taxonomy = Taxonomy(str(ROOT / "data" / "kb" / "skill_taxonomy.yaml"))
    rule = RuleBaselineExtractor(taxonomy)
    matcher = TfidfMatcher().fit([s.name for s in taxonomy.all_skills()])
    transfer = yaml.safe_load((ROOT / "data" / "kb" / "transfer_map.yaml").read_text(encoding="utf-8"))
    resources = yaml.safe_load((ROOT / "data" / "kb" / "learning_resources.yaml").read_text(encoding="utf-8"))
    analyzer = SkillGapAnalyzer(taxonomy, transfer_map=transfer, resources=resources, matcher=matcher)
    return taxonomy, rule, analyzer


@st.cache_data
def load_jobs():
    p = ROOT / "data" / "processed" / "jobs.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()]


@st.cache_data
def extract_corpus():
    taxonomy, rule, _ = load_core()
    rows = []
    for j in load_jobs():
        spans = rule.extract_spans(j["job_id"], j.get("jd_clean") or j.get("jd_text", ""))
        rows.append({
            "job_id": j["job_id"], "title": j.get("title", ""),
            "company": j.get("company", ""), "location": j.get("location", ""),
            "department": j.get("department", ""), "publish_time": j.get("publish_time", ""),
            "skills": [s.skill_id for s in spans],
        })
    return rows


def compute_demand(rows):
    total = len(rows)
    if not total:
        return {}
    cnt = Counter()
    for r in rows:
        for sid in set(r["skills"]):
            cnt[sid] += 1
    return {sid: c / total for sid, c in cnt.items()}


def _skill_name(taxonomy, sid):
    sk = taxonomy.by_id(sid)
    return sk.name if sk else sid


def _match_job(r, search):
    """多关键词(AND) + 模糊匹配：匹配标题(含翻译)/地点，支持英文拼写容错。"""
    if not search.strip():
        return True
    title = _translate_title(r["title"]).lower()
    title_raw = str(r["title"]).lower()
    loc = (r.get("location") or "").lower()
    kws = [k for k in re.split(r"[\s,，、]+", search.strip().lower()) if k]
    # 标题/地点拆词，供拼写容错的模糊匹配
    words = re.findall(r"[a-z0-9]+", f"{title} {title_raw} {loc}")
    for kw in kws:
        if kw in title or kw in title_raw or kw in loc:
            continue
        if difflib.get_close_matches(kw, words, n=1, cutoff=0.7):
            continue
        return False
    return True


def _fmt_time(pt):
    """发布时间统一成 YYYY-MM-DD。"""
    s = str(pt).strip()
    if not s:
        return ""
    m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return s[:10]


def _job_label(r):
    """岗位下拉显示标签：标题 · 地点 · 部门 · 发布时间。"""
    parts = [_translate_title(r["title"]), r.get("location") or ""]
    dep = r.get("department") or ""
    if dep:
        parts.append(dep)
    pt = _fmt_time(r.get("publish_time") or "")
    if pt:
        parts.append(pt)
    return " · ".join([p for p in parts if p])


def page_graph(taxonomy, rows):
    st.header("技能图谱")
    if not rows:
        st.warning("暂无数据，请先运行 `python -m src.data.build_dataset`")
        return

    # 公司筛选
    companies = ["全部"] + sorted({r["company"] for r in rows})
    company = st.selectbox("🏢 筛选公司", companies)
    if company != "全部":
        rows = [r for r in rows if r["company"] == company]

    demand = compute_demand(rows)
    c1, c2, c3 = st.columns(3)
    c1.metric("JD 数量", len(rows))
    c2.metric("技能种类", len(demand))
    c3.metric("覆盖公司", len({r["company"] for r in rows}))

    import pandas as pd

    st.subheader("高频技能 Top 20")
    top = sorted(demand.items(), key=lambda x: -x[1])[:20]
    df = pd.DataFrame({"需求占比": [v for _, v in top]},
                      index=[_skill_name(taxonomy, sid) for sid, _ in top])
    st.bar_chart(df)

    st.subheader("技能类别分布")
    cat_cnt = Counter()
    for sid, ratio in demand.items():
        sk = taxonomy.by_id(sid)
        cat_cnt[(sk.category_name if sk else "未知")] += 1
    st.bar_chart(pd.DataFrame({"技能数": list(cat_cnt.values())},
                              index=list(cat_cnt.keys())))

    if st.checkbox("显示技能共现网络"):
        st.components.v1.html(_cooccurrence_html(taxonomy, rows), height=560, scrolling=True)


def _cooccurrence_html(taxonomy, rows):
    try:
        from pyvis.network import Network
    except Exception:
        return "<p>pyvis 未安装</p>"
    demand = compute_demand(rows)
    top_ids = {sid for sid, _ in sorted(demand.items(), key=lambda x: -x[1])[:25]}
    net = Network(height="540px", width="100%", directed=False, cdn_resources="in_line")
    for sid in top_ids:
        net.add_node(sid, label=_skill_name(taxonomy, sid), size=10 + 20 * demand.get(sid, 0))
    edges = set()
    for r in rows:
        skills = [s for s in set(r["skills"]) if s in top_ids]
        for i in range(len(skills)):
            for j in range(i + 1, len(skills)):
                edges.add(tuple(sorted((skills[i], skills[j]))))
    for a, b in edges:
        net.add_edge(a, b)
    return net.generate_html()
def page_resume(taxonomy, rule, analyzer):
    st.header("简历匹配")
    uploaded = st.file_uploader("上传简历附件（支持 PDF / DOCX / TXT）",
                                type=["pdf", "docx", "txt", "md"])
    if uploaded is None:
        st.info("上传你的简历文件，系统会解析文本并提取技能")
        return

    try:
        from src.data.file_parser import parse_bytes
        text = parse_bytes(uploaded.name, uploaded.getvalue())
    except Exception as e:  # noqa: BLE001
        st.error(f"文件解析失败：{e}")
        return

    with st.expander("查看解析出的文本", expanded=False):
        st.text(text[:5000] + ("…" if len(text) > 5000 else ""))

    # 结构化解析（正则 + DeepSeek LLM 增强，无 key 自动降级正则）
    from src.data.resume_parser import ats_suggestions, parse_resume_full
    profile = parse_resume_full(text)

    st.subheader("📋 结构化信息解析")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("姓名", profile.name or "未识别")
    c2.metric("最高学历", profile.highest_degree or "未识别")
    c3.metric("工作年限", (profile.work_years + " 年") if profile.work_years else "未识别")
    c4.metric("邮箱", profile.email or "未识别")
    if profile.phone:
        st.caption("📱 手机号：" + profile.phone)
    if profile.schools:
        st.caption("🏫 毕业院校：" + "、".join(profile.schools))
    if profile.majors:
        st.caption("🎓 所学专业：" + "、".join(profile.majors))
    if profile.experiences:
        st.markdown("**💼 工作/项目经历：**")
        for e in profile.experiences:
            if isinstance(e, dict):
                comp = e.get("company") or ""
                title = e.get("title") or ""
                dur = e.get("duration") or ""
                line = " · ".join(x for x in [comp, title, dur] if x)
                if line:
                    st.markdown(f"- {line}")

    if st.button("提取技能"):
        spans = rule.extract_spans("user", text)
        st.session_state["user_skills"] = [s.skill_text for s in spans]
        st.session_state["user_skill_ids"] = [s.skill_id for s in spans]

        st.subheader("识别到的 AI 技能")
        if spans:
            by_cat = {}
            for s in spans:
                sk = taxonomy.by_id(s.skill_id)
                name = sk.name if sk else s.skill_text
                by_cat.setdefault(s.category, []).append(name)
            for cat, items in sorted(by_cat.items()):
                st.markdown(f"**{cat}**：{'、'.join(items)}")
        else:
            st.info("未识别到编程/算法类技能（道桥等工科背景通常如此，很正常）")

        st.subheader("道桥背景 → AI 技能迁移建议")
        bg = analyzer.detect_background(text)
        if bg:
            for b in bg:
                with st.expander(f"{b['source_skill']}  →  {'、'.join(b['targets'])}"):
                    st.caption(f"匹配关键词：{'、'.join(b['keywords'])}")
                    st.write(b["rationale"])
                    st.write("行动建议：" + b["action"])
        else:
            st.caption("未匹配到道桥背景关键词")

        st.subheader("🎯 ATS 改进建议")
        tips = ats_suggestions(profile, text, [s.skill_text for s in spans])
        if tips:
            for t in tips:
                if t["level"] == "critical":
                    st.error("⚠️ " + t["tip"])
                else:
                    st.info("💡 " + t["tip"])
        else:
            st.success("简历信息较完整，未发现明显 ATS 风险")


def page_gap(taxonomy, analyzer, rows):
    st.header("差距报告")
    if not rows:
        st.warning("暂无数据，请先运行 `python -m src.data.build_dataset`")
        return

    demand = compute_demand(rows)

    # 1) 先选公司
    companies = sorted({r["company"] for r in rows})
    company = st.selectbox("🏢 选择公司", companies)

    # 2) 搜索岗位（该公司内按标题/地点关键词过滤）
    company_jobs = [r for r in rows if r["company"] == company]
    search = st.text_input("🔍 搜索岗位（支持多关键词空格分隔 + 模糊匹配，可留空）", "")
    if search.strip():
        company_jobs = [r for r in company_jobs if _match_job(r, search)]

    if not company_jobs:
        st.warning("该公司没有匹配的岗位，请换关键词或换公司")
        return

    # 3) 再选该公司内的具体岗位
    options = {_job_label(r): r for r in company_jobs}
    label = st.selectbox("📋 选择岗位", list(options))
    target = options[label]

    jd_skills = []
    for sid in sorted(set(target["skills"])):
        sk = taxonomy.by_id(sid)
        jd_skills.append({"skill_id": sid, "name": sk.name if sk else sid,
                          "is_must": demand.get(sid, 0) >= 0.4})

    user_skills = st.session_state.get("user_skills", [])
    user_input = st.text_input("或直接输入技能（逗号分隔，留空则用「简历匹配」结果）", "")
    if user_input:
        user_skills = [x.strip() for x in user_input.replace("，", ",").split(",") if x.strip()]

    if st.button("生成差距报告"):
        if not user_skills:
            st.warning("请先在「简历匹配」提取技能，或在上方输入技能")
            return
        rep = analyzer.analyze(user_skills, jd_skills, demand=demand)
        st.metric("匹配度", f"{rep.match_score}%")
        st.markdown(f"命中 **{rep.matched_total}** 项 / 缺失 **{rep.missing_total}** 项")

        if not rep.missing:
            st.success("🎉 已覆盖目标岗位的全部技能，暂无差距")
            return

        p0 = [m for m in rep.missing if m.priority == "P0"]
        p1 = [m for m in rep.missing if m.priority == "P1"]
        p2 = [m for m in rep.missing if m.priority == "P2"]

        # ---- 优先补充建议 ----
        st.subheader("🎯 优先补充建议")
        top = rep.missing[:3]
        if top:
            names = "、".join(f"<b>{m.name}</b>" for m in top)
            st.markdown(
                f'<div style="background:#e8f4fd; border:1px solid #b6d9f2; border-radius:8px;'
                f'padding:12px 16px; margin:8px 0;">'
                f'<div style="font-weight:700; color:#1f6feb;">💡 建议优先补充</div>'
                f'<div style="margin-top:4px; color:#333;">{names}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        for emoji, label, items, desc in [
            ("🔴", "P0 先学", p0, "硬性门槛 / 高频需求，最优先补齐"),
            ("🟠", "P1 进阶", p1, "重要且常用，补上后竞争力明显提升"),
            ("🔵", "P2 可选", p2, "加分项，有余力再补"),
        ]:
            if items:
                st.markdown(f"#### {emoji} {label} · {desc}（{len(items)} 项）")
                for m in items:
                    st.markdown(_gap_card(m), unsafe_allow_html=True)

        # ---- 完整缺失技能清单 ----
        st.subheader(f"📋 缺失技能清单（共 {rep.missing_total} 项）")
        for m in rep.missing:
            header = f"{m.name} · {m.priority} · 重要度{_stars(m.importance, 5)} 难度{_stars(m.difficulty, 4)}"
            with st.expander(header):
                st.markdown(_priority_badge(m.priority) + f" **{m.name}**", unsafe_allow_html=True)
                st.write(m.why)
                st.caption(f"行业重要度：{_stars(m.importance, 5)}（5 为最核心） ｜ 学习难度：{_stars(m.difficulty, 4)}（4 为最难）")
                if m.transfer_hint:
                    st.info("道桥迁移：" + m.transfer_hint)
                for r in m.resources:
                    st.markdown(f"- [{r.get('title')}]({r.get('url')})")


def main():
    _inject_css()
    taxonomy, rule, analyzer = load_core()
    rows = extract_corpus()
    st.sidebar.markdown("## 🎯 AI 岗位技能差距分析")
    st.sidebar.caption("面向非科班求职者的技能诊断与学习规划")
    st.sidebar.markdown("---")
    page = st.sidebar.radio("页面", ["技能图谱", "简历匹配", "差距报告"])
    if page == "技能图谱":
        page_graph(taxonomy, rows)
    elif page == "简历匹配":
        page_resume(taxonomy, rule, analyzer)
    else:
        page_gap(taxonomy, analyzer, rows)


main()