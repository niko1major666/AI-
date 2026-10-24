import copy

from scripts.validate_kb import validate_repo, validate_resources, validate_taxonomy

TAX = {
    "categories": [{"id": "PROG", "name": "编程语言"}, {"id": "ML", "name": "机器学习算法"}],
    "skills": [
        {"id": "PROG.PYTHON", "name": "Python", "category": "PROG",
         "aliases": ["py"], "difficulty": 1, "importance": 5},
        {"id": "ML.DL", "name": "深度学习", "category": "ML",
         "aliases": ["Deep Learning"], "difficulty": 2, "importance": 4},
    ],
}

RES = {
    "version": 2,
    "resources": [
        {"skill_id": "PROG.PYTHON", "items": [
            {"type": "course", "title": "Python 官方教程", "url": "https://docs.python.org/zh-cn/3/tutorial/"},
            {"type": "book", "title": "流畅的 Python", "url": ""},
        ]},
    ],
}


def _bad_tax(mutator):
    data = copy.deepcopy(TAX)
    mutator(data)
    return validate_taxonomy(data)


def test_valid_fixtures_pass():
    assert validate_taxonomy(TAX) == []
    assert validate_resources(RES, {"PROG.PYTHON", "ML.DL"}) == []


def test_repo_kb_is_valid():
    """仓库里的真实词表/资源必须通过校验（CI 与测试双重把关）。"""
    assert validate_repo() == []


def test_duplicate_id_detected():
    errs = _bad_tax(lambda d: d["skills"].append(dict(d["skills"][0], name="Python3")))
    assert any("id 重复" in e for e in errs)


def test_bad_category_detected():
    errs = _bad_tax(lambda d: d["skills"][0].update(category="NOPE"))
    assert any("category" in e for e in errs)


def test_difficulty_range_detected():
    errs = _bad_tax(lambda d: d["skills"][0].update(difficulty=9))
    assert any("difficulty" in e for e in errs)


def test_duplicate_name_and_alias_conflict_detected():
    errs = _bad_tax(lambda d: d["skills"][1].update(name="Python"))
    assert any("name" in e for e in errs)
    errs = _bad_tax(lambda d: d["skills"][1].update(aliases=["py"]))
    assert any("别名" in e for e in errs)


def test_empty_alias_or_name_detected():
    errs = _bad_tax(lambda d: d["skills"][0].update(aliases=["  "]))
    assert any("空别名" in e for e in errs)
    errs = _bad_tax(lambda d: d["skills"][0].update(name=""))
    assert any("name 为空" in e for e in errs)


def test_resources_unknown_skill_and_duplicate_block():
    data = copy.deepcopy(RES)
    data["resources"].append({"skill_id": "NOPE.X", "items": [{"title": "x", "url": ""}]})
    data["resources"].append({"skill_id": "PROG.PYTHON", "items": [{"title": "y", "url": ""}]})
    errs = validate_resources(data, {"PROG.PYTHON", "ML.DL"})
    assert any("不在技能词表" in e for e in errs)
    assert any("重复出现" in e for e in errs)


def test_resources_empty_items_title_and_url():
    data = {"resources": [{"skill_id": "PROG.PYTHON", "items": []},
                          {"skill_id": "ML.DL", "items": [
                              {"title": "", "url": ""},
                              {"title": "a", "url": "ftp://x"},
                              {"title": "a", "url": ""}]}]}
    errs = validate_resources(data, {"PROG.PYTHON", "ML.DL"})
    assert any("items 为空" in e for e in errs)
    assert any("空 title" in e for e in errs)
    assert any("非法 url" in e for e in errs)
    assert any("title「a」重复" in e for e in errs)


def test_resources_missing_list():
    assert validate_resources({}, set()) == ["resources: 缺少 resources 列表"]
