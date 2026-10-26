from src.matcher.job_favorites import (
    FAVORITE_LIMIT,
    decode_favorites,
    encode_favorites,
    hydrate_favorites,
    is_favorited,
    make_favorite,
    remove_favorite,
    toggle_favorite,
)


def _job(jid="j1", company="腾讯", title="大模型算法工程师", location="北京"):
    return {"job_id": jid, "company": company, "title": title, "location": location}


def test_make_favorite_keeps_display_fields():
    fav = make_favorite(_job())
    assert fav == {"job_id": "j1", "company": "腾讯", "title": "大模型算法工程师", "location": "北京"}
    # 只留可序列化/可展示字段，并去掉首尾空白
    fav2 = make_favorite({"job_id": " a ", "company": " 字节 ", "title": " 算法 ", "salary": "30k"})
    assert fav2 == {"job_id": "a", "company": "字节", "title": "算法", "location": ""}


def test_toggle_add_then_remove():
    favs, action = toggle_favorite([], _job())
    assert action == "added" and len(favs) == 1
    assert is_favorited(favs, _job())

    favs, action = toggle_favorite(favs, _job())
    assert action == "removed" and favs == []


def test_toggle_dedups_by_company_and_normalized_title():
    # 同一岗位多渠道重复（job_id 不同、标题空格不同）只占一个位置
    favs, action = toggle_favorite([], _job(jid="a", title="大模型 算法工程师"))
    assert action == "added"
    favs2, action = toggle_favorite(favs, _job(jid="b", title="大模型算法工程师 "))
    assert action == "removed"
    assert favs2 == []


def test_toggle_respects_limit():
    favs = [make_favorite(_job(jid=f"j{i}", title=f"岗位{i}")) for i in range(FAVORITE_LIMIT)]
    out, action = toggle_favorite(favs, _job(jid="new", title="新岗位"))
    assert action == "full"
    assert len(out) == FAVORITE_LIMIT
    assert not is_favorited(out, _job(jid="new", title="新岗位"))


def test_remove_favorite():
    favs = [make_favorite(_job()), make_favorite(_job(jid="b", title="数据分析"))]
    out = remove_favorite(favs, _job())
    assert [f["job_id"] for f in out] == ["b"]


def test_encode_decode_roundtrip_and_dedup():
    favs = [
        make_favorite(_job(jid="a")),
        make_favorite(_job(jid="a")),
        make_favorite(_job(jid="b", title="数据分析")),
    ]
    raw = encode_favorites(favs)
    assert raw == "a,b"
    assert decode_favorites(raw) == ["a", "b"]
    # 兼容竖线分隔（旧链接）并去重
    assert decode_favorites("a|b,c,a") == ["a", "b", "c"]
    assert decode_favorites("") == []


def test_encode_respects_limit():
    favs = [make_favorite(_job(jid=f"j{i}", title=f"岗位{i}")) for i in range(FAVORITE_LIMIT + 5)]
    assert len(decode_favorites(encode_favorites(favs))) == FAVORITE_LIMIT


def test_hydrate_by_job_id_preserves_order_and_drops_unknown():
    rows = [_job(jid="a"), _job(jid="b", title="数据分析")]
    out = hydrate_favorites(["b", "missing", "a"], rows)
    assert [f["job_id"] for f in out] == ["b", "a"]
    assert out[0]["title"] == "数据分析"


def test_is_favorited_ignores_bad_entries():
    assert not is_favorited([None, "x", {}], _job())
    assert not is_favorited(None, _job())
