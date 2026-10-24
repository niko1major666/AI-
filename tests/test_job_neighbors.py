from src.matcher.job_neighbors import proxy_skills, title_similarity


def _rows():
    return [
        {"job_id": "t", "title": "推荐算法工程师", "company": "快手", "skills": []},
        {"job_id": "1", "title": "推荐算法工程师（社招）", "company": "快手", "skills": ["A", "B"]},
        {"job_id": "2", "title": "推荐算法工程师-视频", "company": "快手", "skills": ["A", "C"]},
        {"job_id": "3", "title": "推荐算法工程师", "company": "快手", "skills": ["A", "B"]},
        {"job_id": "9", "title": "推荐算法工程师", "company": "腾讯", "skills": ["Z"]},
    ]


def test_title_similarity_is_character_level():
    assert title_similarity("推荐算法工程师", "推荐算法工程师") == 1.0
    assert title_similarity("推荐算法工程师", "测试开发工程师") < 0.6


def test_proxy_skills_uses_same_company_neighbors():
    rows = _rows()
    ids, sources = proxy_skills(rows, rows[0])
    # A 被 3 个邻居提到、B 被 2 个提到、C 只被 1 个提到（3 个邻居时阈值为 2）
    assert set(ids) == {"A", "B"}
    assert len(sources) == 3
    assert "Z" not in ids          # 其他公司的岗位不参与代理


def test_proxy_skills_returns_empty_without_neighbors():
    rows = [{"job_id": "t", "title": "算法工程师", "company": "独家公司", "skills": []}]
    assert proxy_skills(rows, rows[0]) == ([], [])


def test_proxy_skills_ignores_neighbors_without_skills():
    rows = _rows() + [{"job_id": "4", "title": "推荐算法工程师", "company": "快手", "skills": []}]
    _, sources = proxy_skills(rows, rows[0])
    assert len(sources) == 3       # 零技能的邻居不作为来源
