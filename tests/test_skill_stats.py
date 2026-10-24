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
