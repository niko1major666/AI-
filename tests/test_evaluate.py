from src.extractor.evaluate import compute_span_f1, micro_average


def test_exact_f1_perfect():
    r = compute_span_f1([(0, 6), (7, 10)], [(0, 6), (7, 10)])
    assert r.f1 == 1.0
    assert r.tp == 2 and r.fp == 0 and r.fn == 0


def test_exact_f1_partial():
    r = compute_span_f1([(0, 6), (7, 10)], [(0, 6), (20, 25)])
    assert r.tp == 1 and r.fp == 1 and r.fn == 1
    assert r.precision == 0.5
    assert r.recall == 0.5


def test_overlap_f1():
    r = compute_span_f1([(0, 6)], [(1, 5)], mode="overlap")
    assert r.tp == 1
    assert r.f1 == 1.0


def test_empty_pred():
    r = compute_span_f1([(0, 6)], [])
    assert r.precision == 0.0 and r.recall == 0.0 and r.f1 == 0.0


def test_micro_average():
    r1 = compute_span_f1([(0, 6)], [(0, 6)])
    r2 = compute_span_f1([(0, 6)], [])
    agg = micro_average([r1, r2])
    # tp=1, fp=0, fn=1 => P=1.0 R=0.5 F1=0.667
    assert agg.tp == 1 and agg.fn == 1
    assert agg.precision == 1.0
    assert agg.recall == 0.5
    assert abs(agg.f1 - 0.6667) < 1e-3
