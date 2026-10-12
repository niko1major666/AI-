from src.matcher.tfidf_matcher import TfidfMatcher


def test_tfidf_exact_and_rank():
    m = TfidfMatcher()
    m.fit(["Python", "PyTorch", "分布式训练", "向量数据库", "Transformer"])
    hits = m.search("python 编程", top_k=2)
    assert hits[0][0] == "Python"
    assert hits[0][1] > 0


def test_tfidf_chinese():
    m = TfidfMatcher()
    m.fit(["分布式训练", "向量数据库", "数据清洗"])
    hits = m.search("分布式训练", top_k=1)
    assert hits[0][0] == "分布式训练"
    assert hits[0][1] > 0.5


def test_tfidf_requires_fit():
    m = TfidfMatcher()
    try:
        m.search("x")
        assert False, "应抛异常"
    except RuntimeError:
        pass
