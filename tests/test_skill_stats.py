from src.data.skill_stats import demand_by_skill, demand_matrix, top_skill_ids


def _rows():
    return [
        {"company": "A", "skills": ["PROG.PYTHON", "ML.DL"]},
        {"company": "A", "skills": ["PROG.PYTHON"]},
        {"company": "B", "skills": ["ML.DL"]},
        {"company": "C", "skills": []},
    ]


def test_demand_by_skill_uses_all_jobs_as_denominator():
    d = demand_by_skill(_rows())
    assert d["PROG.PYTHON"] == 0.5          # 2 / 4（含零技能岗位）
    assert d["ML.DL"] == 0.5


def test_empty_rows():
    assert demand_by_skill([]) == {}
    assert top_skill_ids([]) == []
    m = demand_matrix([])
    assert m == {"skills": [], "companies": [], "values": []}


def test_top_skill_ids_sorted_and_limited():
    rows = [{"company": "A", "skills": ["PROG.PYTHON"]},
            {"company": "A", "skills": ["PROG.PYTHON"]},
            {"company": "A", "skills": ["ML.DL"]}]
    assert top_skill_ids(rows, 1) == ["PROG.PYTHON"]
    assert top_skill_ids(rows, 10)[0] == "PROG.PYTHON"


def test_matrix_alignment_and_per_company_ratio():
    m = demand_matrix(_rows(), top_n=2)
    # 同占比按 id 升序（确定性排序）
    assert m["skills"] == ["ML.DL", "PROG.PYTHON"]
    assert m["companies"] == ["A", "B", "C"]
    ia, ib = m["companies"].index("A"), m["companies"].index("B")
    assert m["values"][ia] == [0.5, 1.0]              # A: DL 1/2, Python 2/2
    assert m["values"][ib] == [1.0, 0.0]              # B: 只有 DL
    # 每个公司的占比都按该公司 JD 数为分母
    ic = m["companies"].index("C")
    assert m["values"][ic] == [0.0, 0.0]


def test_matrix_companies_sorted_by_job_count_desc():
    """行序：JD 数多的公司在前，同数量按名称升序（小样本的 0%/100% 不占据首屏）。"""
    rows = [{"company": c, "skills": ["PROG.PYTHON"]} for c in ("A", "A", "A", "B", "B", "C")]
    m = demand_matrix(rows, top_n=1)
    assert m["companies"] == ["A", "B", "C"]
    # A 有 3 条 JD，若按字母序则会得到同样的结果，故再加一组「字母序相反」的用例
    rows2 = [{"company": c, "skills": ["PROG.PYTHON"]} for c in ("B", "B", "A")]
    assert demand_matrix(rows2, top_n=1)["companies"] == ["B", "A"]
