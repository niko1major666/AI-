"""Streamlit 前端：技能图谱 / 简历匹配 / 差距报告。"""
from __future__ import annotations

import json
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


def page_graph(taxonomy, rows):
    st.header("技能图谱")
    if not rows:
        st.warning("暂无数据，请先运行 `python -m src.data.build_dataset`")
        return

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


def page_gap(taxonomy, analyzer, rows):
    st.header("差距报告")
    if not rows:
        st.warning("暂无数据，请先运行 `python -m src.data.build_dataset`")
        return

    demand = compute_demand(rows)
    options = {f"{r['company']} · {_translate_title(r['title'])} ({r['job_id']})": r for r in rows}
    label = st.selectbox("目标岗位", list(options))
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
        for m in rep.missing:
            with st.expander(f"{m.name}（score={m.priority_score}）"):
                st.markdown(_priority_badge(m.priority) + f" **{m.name}**", unsafe_allow_html=True)
                st.write(m.why)
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