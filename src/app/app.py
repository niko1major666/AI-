"""Streamlit 前端：技能图谱 / 简历匹配 / 差距报告。"""
from __future__ import annotations

import difflib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import streamlit as st

# 云端部署兼容：把项目根目录加入 sys.path（Streamlit Cloud 的 cwd 可能不在 sys.path）
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.translate import translate_title as _translate_title
from src.matcher.jd_requirements import judge_requirements
from src.matcher.job_favorites import (
    FAVORITE_LIMIT,
    decode_favorites,
    encode_favorites,
    hydrate_favorites,
    is_favorited,
    remove_favorite,
    toggle_favorite,
)
from src.matcher.job_neighbors import proxy_skills

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


def _file_fingerprint(rel_path: str) -> tuple[str, int, int]:
    """文件指纹：路径 + mtime_ns + 大小，用作 Streamlit 缓存键的一部分。

    `@st.cache_data` / `@st.cache_resource` 默认只按函数代码与显式参数缓存：
    数据文件被替换后，长驻进程（尤其云端）仍会返回旧缓存，表现为
    「代码是新版、JD 数量/公司/技能图谱却是旧版」。把指纹作为参数后，
    文件一变缓存键就变，无需手动重启应用。

    注意：参数名不能以下划线开头——Streamlit 会跳过这类参数、不参与哈希。
    """
    p = ROOT / rel_path
    try:
        s = p.stat()
    except OSError:
        return str(p), 0, 0
    return str(p), s.st_mtime_ns, s.st_size


@st.cache_resource
def _load_core_cached(taxonomy_path: str, mtime_ns: int, size: int):
    from src.extractor.rule_baseline import RuleBaselineExtractor
    from src.skillkb.loader import Taxonomy

    taxonomy = Taxonomy(taxonomy_path)
    return taxonomy, RuleBaselineExtractor(taxonomy)


def load_core():
    """轻量核心：词表 + 规则抽取器。

    刻意不在这里建 TfidfMatcher / SkillGapAnalyzer——它们要 import sklearn
    （冷启动 1.5–4.5s），而默认首屏「技能图谱」用不到。需要时用 load_engine()。
    """
    return _load_core_cached(*_file_fingerprint("data/kb/skill_taxonomy.yaml"))


@st.cache_resource
def _load_engine_cached(taxonomy_path: str, tax_mtime_ns: int, tax_size: int,
                        resources_path: str, res_mtime_ns: int, res_size: int):
    import yaml

    from src.matcher.gap_analyzer import SkillGapAnalyzer
    from src.matcher.tfidf_matcher import TfidfMatcher

    taxonomy, _rule = _load_core_cached(taxonomy_path, tax_mtime_ns, tax_size)
    matcher = TfidfMatcher().fit([s.name for s in taxonomy.all_skills()])
    resources = yaml.safe_load(Path(resources_path).read_text(encoding="utf-8"))
    return SkillGapAnalyzer(taxonomy, resources=resources, matcher=matcher)


def load_engine():
    """重量引擎：TF-IDF 匹配 + 差距分析（只有「简历匹配」「差距报告」页需要）。"""
    return _load_engine_cached(
        *_file_fingerprint("data/kb/skill_taxonomy.yaml"),
        *_file_fingerprint("data/kb/learning_resources.yaml"),
    )


@st.cache_data
def _load_jobs_cached(path: str, mtime_ns: int, size: int):
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").split("\n") if x.strip()]


def load_jobs():
    return _load_jobs_cached(*_file_fingerprint("data/processed/jobs.jsonl"))


@st.cache_data
def _extract_corpus_cached(path: str, mtime_ns: int, size: int,
                           taxonomy_path: str, taxonomy_mtime_ns: int, taxonomy_size: int):
    """全语料抽取：技能集合 + JD 内强调度(tf) + must/nice 判定（结果缓存，冷启动只算一次）。

    判 must 不能再用「全语料需求占比 ≥ 40%」——实测最高只有 36.1%，恒为 False，
    导致 P0 分组永远为空。改为按 JD 文本判定，见 src/matcher/jd_requirements.py。
    """
    taxonomy, rule = _load_core_cached(taxonomy_path, taxonomy_mtime_ns, taxonomy_size)
    rows, texts = [], []
    for j in _load_jobs_cached(path, mtime_ns, size):
        text = j.get("jd_clean") or j.get("jd_text", "")
        spans, counts = rule.extract(j["job_id"], text)
        rows.append({
            "job_id": j["job_id"], "title": j.get("title", ""),
            "company": j.get("company", ""), "location": j.get("location", ""),
            "department": j.get("department", ""), "publish_time": j.get("publish_time", ""),
            "skills": [s.skill_id for s in spans],
            "skill_tf": counts,
            "_spans": [(s.skill_id, s.start) for s in spans],
        })
        texts.append(text)
    demand = compute_demand(rows)
    for r, text in zip(rows, texts):
        judged = judge_requirements(text, r.pop("_spans"), demand)
        r["must_skills"] = sorted(sid for sid, info in judged.items() if info["is_must"])
        r["must_evidence"] = {sid: info["evidence"] for sid, info in judged.items()
                              if info["is_must"] and info["evidence"]}
    return rows


def extract_corpus():
    return _extract_corpus_cached(
        *_file_fingerprint("data/processed/jobs.jsonl"),
        *_file_fingerprint("data/kb/skill_taxonomy.yaml"),
    )


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


# ---- 岗位收藏（求职短名单）----
def _favorites() -> list:
    return list(st.session_state.get("favorite_jobs") or [])


def _save_favorites(favs) -> None:
    """收藏同步到 session + 链接参数：刷新/书签不丢（无后端存储）。"""
    st.session_state["favorite_jobs"] = list(favs)
    try:
        if favs:
            st.query_params["fav"] = encode_favorites(favs)
        elif "fav" in st.query_params:
            del st.query_params["fav"]
    except Exception:  # noqa: BLE001
        pass


def _init_favorites(rows) -> None:
    """首次进入时从 ?fav=job_id,... 还原收藏（语料重建后失效的 id 自动丢弃）。"""
    if st.session_state.get("favorites_loaded"):
        return
    try:
        raw = st.query_params.get("fav") or ""
    except Exception:  # noqa: BLE001
        raw = ""
    st.session_state["favorite_jobs"] = hydrate_favorites(decode_favorites(raw), rows)
    st.session_state["favorites_loaded"] = True


def _toggle_favorite(job: dict) -> None:
    favs, action = toggle_favorite(_favorites(), job)
    if action == "full":
        st.warning(f"收藏夹最多 {FAVORITE_LIMIT} 个岗位，请先在左侧「我的收藏」移除一些")
        return
    _save_favorites(favs)
    st.rerun()


def _render_favorite_button(job: dict, key_prefix: str = "") -> None:
    """⭐ 收藏/取消收藏按钮（差距报告页、简历推荐列表共用）。"""
    jid = str(job.get("job_id") or "")
    token = re.sub(r"[^0-9A-Za-z\u4e00-\u9fa5]+",
                   "", f"{job.get('company', '')}{job.get('title', '')}")[:40]
    key = f"{key_prefix}fav_{jid or token}"
    fav = is_favorited(_favorites(), job)
    label = "✅ 已收藏（点击取消）" if fav else "⭐ 收藏该岗位"
    if st.button(label, key=key, help=f"收藏会保存在当前页面链接，最多 {FAVORITE_LIMIT} 个"):
        _toggle_favorite(job)


def _render_favorites_sidebar() -> None:
    """侧边栏收藏夹：列表 + 移除 + 导出（跨页面可见）。"""
    favs = _favorites()
    st.sidebar.markdown("---")
    with st.sidebar.expander(f"⭐ 我的收藏（{len(favs)}/{FAVORITE_LIMIT}）", expanded=False):
        if not favs:
            st.caption("在「差距报告」或「简历匹配」页点「⭐ 收藏该岗位」。收藏会保存在当前页面链接中，刷新或收藏书签都不会丢。")
            return
        for idx, f in enumerate(favs):
            name = _translate_title(str(f.get("title") or "")) or "未命名岗位"
            meta = " · ".join(x for x in [str(f.get("company") or ""), str(f.get("location") or "")] if x)
            c1, c2 = st.columns([0.78, 0.22])
            c1.markdown(f"**{name}**  \n{meta}")
            if c2.button("移除", key=f"fav_remove_{idx}"):
                _save_favorites(remove_favorite(favs, f))
                st.rerun()
        st.download_button(
            "导出收藏（JSON）", json.dumps(favs, ensure_ascii=False, indent=2),
            file_name="job_favorites.json", mime="application/json", key="fav_export",
        )
        st.caption("收藏会随当前页面链接保存；换设备或清空链接会丢失，可导出 JSON 备份。")


def _build_jd_skills(taxonomy, target, demand):
    """把岗位技能转成分析器输入：must 判定（JD 文本驱动）+ 岗位内强调度 tf + 判定依据。"""
    must_ids = set(target.get("must_skills") or [])
    evidence = target.get("must_evidence") or {}
    tf = target.get("skill_tf") or {}
    out = []
    for sid in sorted(set(target.get("skills") or [])):
        sk = taxonomy.by_id(sid)
        out.append({
            "skill_id": sid,
            "name": sk.name if sk else sid,
            "is_must": sid in must_ids,
            "must_evidence": evidence.get(sid, ""),
            "tf": int(tf.get(sid, 1) or 1),
        })
    return out


def _proxy_jd_skills(taxonomy, target, rows, demand):
    """零技能岗位兜底：用同公司相似岗位的技能集推断（无数据驱动 must 证据）。"""
    ids, sources = proxy_skills(rows, target)
    out = []
    for sid in ids:
        sk = taxonomy.by_id(sid)
        ratio = float(demand.get(sid, 0.0) or 0.0)
        out.append({
            "skill_id": sid,
            "name": sk.name if sk else sid,
            "is_must": ratio >= 0.3,
            "must_evidence": f"相似岗位高频（{ratio:.0%}）" if ratio >= 0.3 else "",
            "tf": 1,
        })
    return out, sources


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

    # ---- 公司 × Top 技能（每条 = 该公司 JD 中提到该技能的比例）----
    from src.data.skill_stats import demand_matrix
    matrix = demand_matrix(rows, top_n=12)
    if matrix["skills"]:
        st.subheader("公司 × Top 12 技能")
        st.caption("数值 = 该公司 JD 中提到该技能的比例；条形越长说明该技能在这家公司越是硬通货")
        df_m = pd.DataFrame(
            [[round(v * 100, 1) for v in row] for row in matrix["values"]],
            index=matrix["companies"],
            columns=[_skill_name(taxonomy, sid) for sid in matrix["skills"]],
        )
        st.dataframe(
            df_m,
            height=420,
            column_config={c: st.column_config.ProgressColumn(
                c, min_value=0, max_value=100, format="%.0f%%") for c in df_m.columns},
        )

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
@st.cache_data(show_spinner=False, max_entries=32)
def _resume_profile(text: str):
    """简历结构化解析缓存：同一份简历在后续 rerun 中不再重复调 LLM（原先每次 rerun 都调）。"""
    from src.data.resume_parser import parse_resume_full
    return parse_resume_full(text)


def page_resume(taxonomy, rule, analyzer, rows=None):
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

    # 供「差距报告」页生成针对 P0 的简历补强建议
    st.session_state["resume_text"] = text

    with st.expander("查看解析出的文本", expanded=False):
        st.text(text[:5000] + ("…" if len(text) > 5000 else ""))

    # 结构化解析（正则 + DeepSeek LLM 增强，无 key 自动降级正则）；结果按简历文本缓存
    from src.data.resume_parser import ats_suggestions
    profile = _resume_profile(text)
    # 与「差距报告」联动：把解析出的专业写入会话，报告页据此生成专业相关建议
    st.session_state["user_majors"] = list(profile.majors or [])

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
        from src.data.resume_parser import EXPERIENCE_KIND_LABELS
        groups = [
            ("💼 工作/实习经历", profile.work_experiences),
            ("🚀 项目经历", profile.project_experiences),
            ("📌 其他经历（未识别类型）", profile.other_experiences),
        ]
        for group_label, items in groups:
            if not items:
                continue
            st.markdown(f"**{group_label}（{len(items)} 段）：**")
            for e in items:
                if not isinstance(e, dict):
                    continue
                comp = e.get("company") or ""
                title = e.get("title") or ""
                dur = e.get("duration") or ""
                line = " · ".join(x for x in [comp, title, dur] if x)
                kind = EXPERIENCE_KIND_LABELS.get(str(e.get("kind") or "other"), "")
                tag = f"`{kind}` " if kind and kind != "其他" else ""
                if line:
                    st.markdown(f"- {tag}**{line}**")
                desc = e.get("description") or ""
                if desc:
                    st.markdown(f"  - 职责：{desc}")
                techs = e.get("tech_stack") or []
                if techs:
                    st.markdown(f"  - 技术栈：{'、'.join(techs)}")
                achieves = e.get("achievements") or []
                if achieves:
                    st.markdown("  - 成果：" + "；".join(achieves))

    if st.button("提取技能"):
        spans = rule.extract_spans("user", text)
        # 合并 LLM 解析出的技能（映射到标准词表，补充规则未覆盖的技能）
        known_ids = {s.skill_id for s in spans}
        extra_skills = []
        for name in (profile.skills or []):
            sk = taxonomy.resolve(name)
            if sk and sk.id not in known_ids:
                known_ids.add(sk.id)
                extra_skills.append(sk)
        st.session_state["user_skills"] = [s.skill_text for s in spans] + [s.name for s in extra_skills]
        st.session_state["user_skill_ids"] = [s.skill_id for s in spans] + [s.id for s in extra_skills]

        st.subheader("识别到的 AI 技能")
        all_skills = [
            (s.skill_id, s.category, (taxonomy.by_id(s.skill_id).name if taxonomy.by_id(s.skill_id) else s.skill_text))
            for s in spans
        ] + [(s.id, s.category, s.name) for s in extra_skills]
        if all_skills:
            by_cat = {}
            for _sid, cat, name in all_skills:
                by_cat.setdefault(cat, []).append(name)
            for cat, items in sorted(by_cat.items()):
                st.markdown(f"**{cat}**：{'、'.join(items)}")
        else:
            st.info("未识别到编程/算法类技能，可在简历中补充具体的项目与技术栈")

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

    _render_strength_and_jobs(taxonomy, analyzer, rows or [])


def _recommendations(skill_ids: tuple):
    return _recommendations_cached(
        skill_ids,
        _file_fingerprint("data/processed/jobs.jsonl"),
        _file_fingerprint("data/kb/skill_taxonomy.yaml"),
        _file_fingerprint("data/kb/learning_resources.yaml"),
    )


@st.cache_data(show_spinner=False, max_entries=16)
def _recommendations_cached(skill_ids: tuple, jobs_fingerprint: tuple[str, int, int],
                            taxonomy_fingerprint: tuple[str, int, int],
                            resources_fingerprint: tuple[str, int, int]):
    """简历技能 -> Top 岗位（技能组合 + 语料/词表/资源指纹缓存；任一更新自动重算）。"""
    taxonomy, _rule = load_core()
    analyzer = load_engine()
    from dataclasses import asdict

    from src.matcher.job_recommender import recommend_jobs

    names = [taxonomy.by_id(s).name for s in skill_ids if taxonomy.by_id(s)]
    return [asdict(s) for s in recommend_jobs(names, extract_corpus(), analyzer, top_k=10)]


def _render_strength_and_jobs(taxonomy, analyzer, rows):
    """简历页下半部分：技能画像（C7）+ 反向岗位推荐（C6）。"""
    skill_ids = list(st.session_state.get("user_skill_ids") or [])
    if not skill_ids:
        return
    if not rows:
        return

    import pandas as pd

    from src.matcher.strength_profile import (
        category_profile,
        overall_coverage,
        weakest_categories,
    )

    demand = compute_demand(rows)
    st.subheader("🧭 我的技能画像")
    profile = category_profile(skill_ids, taxonomy, demand)
    cov = overall_coverage(skill_ids, taxonomy, demand)
    weak = weakest_categories(profile, limit=1)
    c1, c2 = st.columns(2)
    c1.metric("需求加权覆盖率", f"{cov:.1%}")
    if weak:
        w = weak[0]
        c2.metric("最大短板类别", w["name"], f"覆盖 {w['coverage']:.0%}")
    st.caption("覆盖率 = 已掌握技能的需求占比之和 ÷ 该类别全部技能的需求占比之和（按全语料 JD）")
    df = pd.DataFrame(
        {"覆盖率": [round(p["coverage"] * 100, 1) for p in profile]},
        index=[p["name"] for p in profile],
    )
    st.bar_chart(df)

    st.subheader("🔎 适合我的岗位 Top 10")
    st.caption("用简历技能反向扫描全语料（同公司 + 同标题去重），按 must/nice 加权匹配度排序")
    with st.spinner("正在扫描全语料岗位…"):
        sugs = _recommendations(tuple(sorted(set(skill_ids))))
    if not sugs:
        st.info("暂未匹配到合适的岗位：先补几项核心技能（Python / PyTorch / 大模型 等）再来看看")
        return
    df_jobs = pd.DataFrame([
        {
            "公司": s["company"],
            "岗位": _translate_title(s["title"]),
            "地点": s["location"],
            "匹配度": f"{s['match_score']:.0f}%",
            "缺口数": s["missing_total"],
            "最该补": "、".join(s["top_missing"]),
        }
        for s in sugs
    ])
    st.dataframe(df_jobs, height=380, hide_index=True,
                 column_config={"匹配度": st.column_config.TextColumn("匹配度")})

    st.markdown("**⭐ 加入收藏夹**")
    fav_labels = {
        f"{s['company']} · {_translate_title(s['title'])} · {s['location']}": s
        for s in sugs
    }
    picked = st.selectbox("选择要收藏的岗位", list(fav_labels),
                          key="rec_fav_pick", label_visibility="collapsed")
    _render_favorite_button(fav_labels[picked], key_prefix="rec_")


def _render_learning_path(taxonomy, rep, meta):
    """规则版学习路径 + 「已学进度」：勾选已掌握技能后立即重排（纯规则，rerun 即生效）。"""
    from src.matcher.learning_path import build_learning_path, format_path_markdown

    st.subheader("📅 学习路径（规则版 · 无需 AI）")
    options = {m.skill_id: f"{m.name} · {m.priority}" for m in rep.missing}
    learned = st.multiselect(
        "✅ 已学进度：勾选已掌握 / 已学完的技能，勾选后会从学习路径移除并重排",
        options=list(options),
        format_func=lambda sid: options[sid],
        key=f"gap_learned_{meta.get('job_id')}",
        help="选项来自本次差距报告的缺失清单；换岗位或重新生成报告后需重新勾选",
    )
    path = build_learning_path(rep.missing, taxonomy=taxonomy, learned=learned)
    st.session_state["gap_path"] = path        # 导出用最新（已重排）的路径
    st.markdown(format_path_markdown(path))
    if path.stages:
        st.caption(
            f"已标记 {len(learned)} 项已掌握，剩余 {path.total_hours} 学时 / 约 "
            f"{path.total_weeks} 周（按每周 10 小时）；学时按技能难度估算，顺序已考虑先修关系。"
            if learned else
            "学时按技能难度估算，顺序已考虑先修关系；更贴合个人情况的版本见下方「AI 解读」。"
        )
    return path


def _render_ai_plan(rep, meta):
    """AI 解读（按「岗位 + 技能」缓存：勾选已学进度触发的 rerun 不会重复调 LLM）。"""
    st.subheader("🤖 AI 解读 + 学习计划")
    key = (meta.get("job_id"), tuple(meta.get("skills") or []))
    if st.session_state.get("gap_interp_key") != key:
        with st.spinner("正在生成 AI 解读与学习计划…"):
            from src.matcher.report_interpreter import interpret_report
            st.session_state["gap_interp"] = interpret_report(
                rep, target_job=meta.get("job_title", ""),
                user_skills=meta.get("skills") or [],
                user_majors=st.session_state.get("user_majors", []),
            )
        st.session_state["gap_interp_key"] = key
    interp = st.session_state.get("gap_interp") or {}
    if interp.get("overview"):
        st.markdown(interp["overview"])
    for stage in interp.get("plan", []):
        st.markdown(f"#### 📅 {stage.get('phase', '')}")
        if stage.get("goal"):
            st.markdown(f"**目标**：{stage['goal']}")
        if stage.get("skills"):
            st.markdown("**技能**：" + "、".join(f"`{s}`" for s in stage["skills"]))
        for act in stage.get("actions", []):
            st.markdown(f"- {act}")
    if interp.get("tips"):
        st.info(interp["tips"])


def _render_gap_export(rep, meta):
    """报告导出（C2）：读 session 中的最新路径，rerun 后按钮仍在。"""
    st.subheader("⬇️ 导出报告")
    from src.app.report_export import report_docx, report_markdown, safe_filename
    cached_path = st.session_state.get("gap_path")
    company_name = meta.get("company", "")
    job_name = meta.get("job_title", "")
    md = report_markdown(rep, company=company_name, job_title=job_name,
                         user_skills=meta.get("skills") or [], learning_path=cached_path)
    col_md, col_docx = st.columns(2)
    col_md.download_button("下载 Markdown（.md）", md,
                           file_name=safe_filename(company_name, job_name, "md"),
                           mime="text/markdown", key="dl_gap_md")
    try:
        docx_bytes = report_docx(rep, company=company_name, job_title=job_name,
                                 user_skills=meta.get("skills") or [],
                                 learning_path=cached_path)
    except ImportError:
        col_docx.caption("未安装 python-docx，暂不支持 Word 导出")
    else:
        col_docx.download_button(
            "下载 Word（.docx）", docx_bytes,
            file_name=safe_filename(company_name, job_name, "docx"),
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key="dl_gap_docx",
        )


def _render_gap_report(taxonomy, rep, meta):
    """渲染已生成的差距报告（从 session 读取：rerun 后报告不再消失，只做规则计算）。"""
    st.metric("匹配度", f"{rep.match_score}%")
    st.markdown(f"命中 **{rep.matched_total}** 项 / 缺失 **{rep.missing_total}** 项"
                f" ｜ JD 硬性要求 **{meta.get('jd_must', 0)}** 项")
    user_majors = st.session_state.get("user_majors", [])
    if user_majors:
        st.caption(f"🎓 已结合简历解析出的专业：{'、'.join(user_majors)}")

    if not rep.missing:
        st.success(f"🎉 该岗位要求的 {meta.get('jd_total', 0)} 项技能你已全部覆盖，暂无差距")
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

    for emoji, group_label, items, desc in [
        ("🔴", "P0 先学", p0, "硬性门槛 / 高频需求，最优先补齐"),
        ("🟠", "P1 进阶", p1, "重要且常用，补上后竞争力明显提升"),
        ("🔵", "P2 可选", p2, "加分项，有余力再补"),
    ]:
        if items:
            st.markdown(f"#### {emoji} {group_label} · {desc}（{len(items)} 项）")
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
            for r in m.resources:
                st.markdown(f"- [{r.get('title')}]({r.get('url')})")

    # ---- 简历补强建议（C5，仅当本次会话上传过简历）----
    resume_text = st.session_state.get("resume_text") or ""
    if resume_text:
        from src.data.resume_advice import build_advice
        advice = build_advice(p0 or rep.missing, taxonomy, resume_text, limit=3)
        if advice:
            st.subheader("✍️ 简历补强建议（针对 P0）")
            for a in advice:
                mark = "✅" if a["status"] == "已有相关经历" else "➕"
                st.markdown(f"{mark} **{a['name']}** · {a['status']}")
                st.caption(a["suggestion"])
                st.caption("项目建议：" + a["project_idea"])

    # ---- 规则版学习路径（C1，不依赖 LLM）+ 已学进度联动 ----
    _render_learning_path(taxonomy, rep, meta)

    # ---- AI 解读 + 学习计划（LLM 优先、模板兜底）----
    _render_ai_plan(rep, meta)


def page_gap(taxonomy, analyzer, rows):
    st.header("差距报告")
    if not rows:
        st.warning("暂无数据，请先运行 `python -m src.data.build_dataset`")
        return

    demand = compute_demand(rows)
    mode = st.radio("分析模式", ["单岗位报告", "多岗位对比"], horizontal=True, key="gap_mode")
    if mode == "多岗位对比":
        page_gap_compare(taxonomy, analyzer, rows, demand)
        return

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
    _render_favorite_button(target, key_prefix="gap_")

    jd_skills = _build_jd_skills(taxonomy, target, demand)
    if not jd_skills:
        # 零技能岗位（列表式短 JD，全语料 25.4%）：用同公司相似岗位兜底，并明确标注来源
        jd_skills, sources = _proxy_jd_skills(taxonomy, target, rows, demand)
        if sources:
            listed = "、".join(sources[:3]) + ("…" if len(sources) > 3 else "")
            st.info(f"该岗位 JD 未抽取出技能要求（列表式短描述），已用同公司 {len(sources)} 个相似岗位推断：{listed}")
    if not jd_skills:
        st.error("该岗位既未抽取出技能要求，也没有可用的相似岗位，无法生成有意义的差距报告，请换一个岗位。")
        return

    user_skills = st.session_state.get("user_skills", [])
    user_input = st.text_input("或直接输入技能（逗号分隔，留空则用「简历匹配」结果）", "")
    if user_input:
        user_skills = [x.strip() for x in user_input.replace("，", ",").split(",") if x.strip()]

    if st.button("生成差距报告"):
        if not user_skills:
            st.warning("请先在「简历匹配」提取技能，或在上方输入技能")
            return
        rep = analyzer.analyze(user_skills, jd_skills, demand=demand)
        # 报告与导出信息存 session：download_button / 已学进度勾选都会 rerun、按钮块会消失；
        # 下面的渲染统一从 session 读，保证交互后报告与学习路径仍然完整可见。
        st.session_state["gap_report"] = rep
        st.session_state.pop("gap_path", None)
        st.session_state.pop("gap_interp", None)
        st.session_state.pop("gap_interp_key", None)
        st.session_state["gap_export"] = {
            "company": company, "job_title": label, "job_id": target.get("job_id"),
            "skills": list(user_skills),
            "jd_must": sum(1 for s in jd_skills if s["is_must"]),
            "jd_total": len(jd_skills),
        }

    rep_cached = st.session_state.get("gap_report")
    meta = st.session_state.get("gap_export") or {}
    # 换了岗位但还没重新生成：不展示上一份岗位的报告
    if rep_cached is None or not meta or meta.get("job_id") != target.get("job_id"):
        return

    _render_gap_report(taxonomy, rep_cached, meta)
    _render_gap_export(rep_cached, meta)


def page_gap_compare(taxonomy, analyzer, rows, demand):
    """多岗位对比（C3）：同一份技能对 2~4 个岗位的匹配度与缺口差异。"""
    from src.matcher.job_compare import compare_jobs

    st.subheader("多岗位对比")
    st.caption("同一份技能，对不同岗位的匹配度与缺口差异（最多 4 个）")
    companies = sorted({r["company"] for r in rows})
    company = st.selectbox("🏢 选择公司", companies, key="cmp_company")
    pool = [r for r in rows if r["company"] == company and r.get("skills")]
    if not pool:
        st.warning("该公司没有可对比的岗位（JD 未抽到技能），换一家公司试试")
        return

    labels = {_job_label(r): r for r in pool}
    picked = st.multiselect("📋 选择 2~4 个岗位", list(labels),
                            default=list(labels)[:2],
                            key=f"cmp_jobs_{company}")
    user_input = st.text_input("技能（逗号分隔，留空则用「简历匹配」结果）", "", key="cmp_skills")
    typed = [x.strip() for x in user_input.replace("，", ",").split(",") if x.strip()]
    user_skills = typed or st.session_state.get("user_skills", [])

    if not st.button("开始对比", key="cmp_run"):
        return
    if len(picked) < 2:
        st.warning("请至少选择 2 个岗位")
        return
    if not user_skills:
        st.warning("请先输入技能，或在「简历匹配」页提取技能")
        return

    targets = []
    for lab in picked[:4]:
        r = labels[lab]
        targets.append({
            "label": lab,
            "company": r["company"],
            "title": _translate_title(r["title"]),
            "jd_skills": _build_jd_skills(taxonomy, r, demand),
            "demand": demand,
        })
    res = compare_jobs(analyzer, user_skills, targets)

    st.markdown(f"**🎯 优先投递**：{res.best_label}（匹配度最高）")
    cols = st.columns(len(res.jobs))
    for col, j in zip(cols, res.jobs):
        col.metric(j.title, f"{j.match_score}%", f"缺 {j.missing_total} 项 · P0 {j.p0_total}")

    import pandas as pd

    st.dataframe(pd.DataFrame([
        {"岗位": j.label, "匹配度": f"{j.match_score}%", "命中": j.matched_total,
         "缺口": j.missing_total, "P0 缺口": j.p0_total}
        for j in res.jobs
    ]), hide_index=True)

    if res.common_missing:
        st.markdown("**共性缺口（所有岗位都缺，优先补）**："
                    + "、".join(f"`{n}`" for n in res.common_missing))
    for lab, names in res.unique_missing.items():
        if names:
            st.caption(f"{lab} 独有缺口：" + "、".join(names))


def main():
    _inject_css()
    taxonomy, rule = load_core()
    rows = extract_corpus()
    _init_favorites(rows)
    st.sidebar.markdown("## 🎯 AI 岗位技能差距分析")
    st.sidebar.caption("面向非科班求职者的技能诊断与学习规划")
    st.sidebar.markdown("---")
    page = st.sidebar.radio("页面", ["技能图谱", "简历匹配", "差距报告"])
    _render_favorites_sidebar()
    if page == "技能图谱":
        # 首屏不触发 load_engine()：避免为「技能图谱」付 sklearn 的冷导入开销
        page_graph(taxonomy, rows)
    elif page == "简历匹配":
        page_resume(taxonomy, rule, load_engine(), rows)
    else:
        page_gap(taxonomy, load_engine(), rows)


main()