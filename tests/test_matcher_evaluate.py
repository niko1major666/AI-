from src.matcher.evaluate import compute_retrieval_metrics


def test_recall_perfect():
    pairs = [("q1", "A"), ("q2", "B")]
    def fn(q, top_k=5):
        return {"q1": ["A", "X"], "q2": ["B"]}[q]
    m = compute_retrieval_metrics(pairs, fn, k=5)
    assert m.recall_at_k == 1.0
    assert m.hit_at_1 == 1.0
    assert m.mrr == 1.0
    assert m.hits == 2


def test_recall_partial():
    pairs = [("q1", "A"), ("q2", "B")]
    def fn(q, top_k=5):
        return {"q1": ["X", "A"], "q2": ["Y", "Z"]}[q]
    m = compute_retrieval_metrics(pairs, fn, k=5)
    # q1 命中(第2位)，q2 未命中
    assert m.recall_at_k == 0.5
    assert m.hit_at_1 == 0.0
    assert abs(m.mrr - 0.25) < 1e-9  # (1/2 + 0)/2


def test_recall_empty_pairs():
    m = compute_retrieval_metrics([], lambda q, top_k=5: [], k=5)
    assert m.recall_at_k == 0.0
    assert m.total == 0

