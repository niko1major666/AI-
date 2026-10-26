"""新数据源体检脚本（`scripts/preflight_new_source.py`）的纯函数与 CLI 回归。

覆盖「扩充新数据最容易静默出错」的五处：job_id 撞车、正文跨源重复、公司写法分裂、
列表式短 JD 的零技能率、CSV 自带 skills 列的词表缺口；另验证合并预测与 FAIL 闸门。
真实语料口径（4582 / 78 / 1162 / 56.5%）由 `test_dataset_snapshot.py` 与
`test_skillkb.py` 锁定，这里不重复硬编码，避免加数据时要改第四处常量。
"""
import csv
import json
from pathlib import Path

import pytest

from scripts.preflight_new_source import (
    build_checks, check_company, check_identity, check_skills_column, check_text,
    exit_code, load_source, main, render, run,
)
from src.skillkb.loader import Taxonomy

ROOT = Path(__file__).resolve().parents[1]
TAXONOMY = ROOT / "data" / "kb" / "skill_taxonomy.yaml"
MAPPING = {k: k for k in ("job_id", "company", "title", "location", "salary",
                          "experience", "education", "jd_text")}
HEADER = "job_id,company,title,location,salary,experience,education,jd_text\n"
LONG_JD = ("负责大模型应用开发，熟悉 Python 与 PyTorch，参与智能体平台建设，"
           "与算法团队协作推进检索增强生成落地，具备良好的工程能力。")
NO_SKILL_JD = ("负责团队协作与项目排期，参与产品需求评审并推动落地，"
               "定期输出复盘文档，协调上下游资源保障交付。")


def _write_csv(tmp_path, name, rows):
    body = "".join(
        f'{jid},{company},{title},北京,30-60K,3年,本科,"{jd}"\n'
        for jid, company, title, jd in rows
    )
    p = tmp_path / name
    p.write_text(HEADER + body, encoding="utf-8")
    return p


def _write_jobs(tmp_path, rows):
    p = tmp_path / "jobs.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
                 encoding="utf-8")
    return p


def _job(job_id, company, title, text):
    return {"job_id": job_id, "company": company, "company_norm": company,
            "title": title, "jd_clean": text, "text_hash": ""}


def test_load_source_filters_short_and_offtopic(tmp_path):
    csv = _write_csv(tmp_path, "new.csv", [
        ("ali_1", "阿里巴巴", "大模型算法工程师", LONG_JD),
        ("ali_2", "阿里巴巴", "大模型算法工程师", "太短"),
        ("ali_3", "某建筑公司", "土建结构工程师", LONG_JD),
    ])
    out = load_source([csv], MAPPING)
    assert out["stats"]["raw_rows"] == 3
    assert out["stats"]["dropped_short"] == 1
    assert out["stats"]["dropped_offtopic"] == 1
    rows = out["rows"]
    assert [r["job_id"] for r in rows] == ["ali_1"]
    assert rows[0]["company_norm"] == "阿里巴巴"
    assert len(rows[0]["text_hash"]) == 12  # sha1_text 取前 12 位


def test_check_identity_flags_collisions_and_dup_ids(tmp_path):
    csv = _write_csv(tmp_path, "new.csv", [
        ("ks_1", "快手", "推荐算法工程师", LONG_JD),
        ("ks_1", "快手", "推荐算法工程师", LONG_JD + "（另一条）"),
        ("", "快手", "推荐算法工程师", NO_SKILL_JD),
    ])
    new = load_source([csv], MAPPING)["rows"]
    existing = [_job("ks_1", "快手", "推荐算法工程师", LONG_JD)]
    res = check_identity(new, existing)
    assert res["missing"] == 1
    assert res["dup_in_new_count"] == 1
    assert res["collision_count"] == 1
    assert res["collisions"] == ["ks_1"]


def test_check_text_reports_both_directions(tmp_path):
    new = load_source([_write_csv(tmp_path, "new.csv", [
        ("ali_1", "阿里巴巴", "大模型算法工程师", LONG_JD),
        ("ali_2", "阿里巴巴", "大模型算法工程师", LONG_JD),
        ("ali_3", "阿里巴巴", "智能体工程师", NO_SKILL_JD),
    ])], MAPPING)["rows"]
    existing = load_source([_write_csv(tmp_path, "old.csv", [
        ("bd_1", "字节跳动", "算法工程师", LONG_JD),
    ])], MAPPING)["rows"]

    res = check_text(new, existing)
    assert res["overlap_count"] == 1          # 一篇正文与现有语料重复
    assert res["dropped_if_new_last"] == 2    # 新源追加在末尾 → 丢这两行
    assert res["dropped_if_new_first"] == 1   # 新源放最前 → 覆盖 1 条旧行
    assert res["dup_in_new_rows"] == 1        # 源内重复 1 行


def test_check_company_flags_alias_variants(tmp_path):
    new = load_source([_write_csv(tmp_path, "new.csv", [
        ("ali_1", "阿里巴巴（中国）有限公司", "算法工程师", LONG_JD),
        ("ali_2", "阿里巴巴", "算法工程师", NO_SKILL_JD),
    ])], MAPPING)["rows"]
    existing = load_source([_write_csv(tmp_path, "old.csv", [
        ("bd_1", "阿里巴巴", "算法工程师", LONG_JD + "（旧）"),
    ])], MAPPING)["rows"]

    res = check_company(new, existing)
    assert res["variants_inner_count"] == 1
    assert sorted(res["variants_inner"]["阿里巴巴"]) == ["阿里巴巴", "阿里巴巴（中国）有限公司"]
    assert res["variants_cross_count"] == 1
    assert res["added_company_count"] == 0


def test_check_skills_column_reports_gaps(tmp_path):
    csv = tmp_path / "hf.csv"
    csv.write_text(
        "job_id,company,title,jd_text,skills\n"
        'x1,某公司,算法工程师,"负责模型训练与部署",'
        '"Python, PyTorch, 量子退火"\n',
        encoding="utf-8")
    tax = Taxonomy(str(TAXONOMY))
    res = check_skills_column([csv], tax)
    assert res["files"] == 1
    assert res["tokens"] == 3
    assert res["resolved"] == 2
    assert res["missing_top"][0][0] == "量子退火"

    plain = _write_csv(tmp_path, "plain.csv", [("p1", "某公司", "算法工程师", LONG_JD)])
    assert check_skills_column([plain], tax) is None


def test_run_predicts_merge_and_zero_skill(tmp_path):
    jobs = _write_jobs(tmp_path, [
        _job("a", "甲", "算法工程师", "熟悉 Python 开发，负责模型训练与上线。"),
        _job("b", "乙", "产品经理", NO_SKILL_JD),
    ])
    csv = _write_csv(tmp_path, "new.csv", [("ali_1", "阿里巴巴", "大模型算法工程师", LONG_JD)])
    report = run([csv], jobs=jobs)

    assert report["existing"]["jobs"] == 2
    assert report["prediction"]["jobs_before"] == 2
    assert report["prediction"]["jobs_after"] == 3
    assert report["prediction"]["kept_new"] == 1
    assert report["prediction"]["zero"]["zero"] == 1
    assert report["prediction"]["companies_after"] == 3
    assert report["prediction"]["skill_coverage"] >= 2  # Python + PyTorch
    assert report["identity"]["collision_count"] == 0
    assert report["company"]["added_company_count"] == 1


def test_build_checks_marks_fail_and_exit_code(tmp_path):
    jobs = _write_jobs(tmp_path, [_job("ks_1", "快手", "推荐算法工程师", LONG_JD)])
    collision = _write_csv(tmp_path, "dup.csv", [("ks_1", "快手", "推荐算法工程师", LONG_JD)])
    report = run([collision], jobs=jobs)

    statuses = {c["name"]: c["status"] for c in report["checks"]}
    assert statuses["job_id 冲突"] == "FAIL"
    assert statuses["合并后零技能占比"] == "FAIL"   # 小语料零技能 0%，落在 20%~28% 之外
    assert exit_code(report["checks"]) == 1
    assert "FAIL" in render(report)
    assert exit_code(build_checks(report)) == 1


def test_cli_main_exit_codes(tmp_path):
    clean_jobs = _write_jobs(tmp_path, [
        _job("a", "甲", "算法工程师", "熟悉 Python 开发，负责模型训练与上线。"),
    ])
    clean = _write_csv(tmp_path, "clean.csv", [("ali_1", "阿里巴巴", "大模型算法工程师", LONG_JD)])
    rc = main(["--source", str(clean), "--jobs", str(clean_jobs),
               "--zero-skill-band", "0,1", "--min-skill-coverage", "1"])
    assert rc == 0

    collide = _write_csv(tmp_path, "collide.csv", [("a", "甲", "算法工程师", LONG_JD)])
    rc = main(["--source", str(collide), "--jobs", str(clean_jobs),
               "--zero-skill-band", "0,1", "--min-skill-coverage", "1"])
    assert rc == 1


def test_run_on_existing_corpus_is_noop(tmp_path):
    """把语料里的若干条原样当「新数据」：应全量识别为重复，合并后规模不变。

    注意不能用 `data/raw/*.csv`：raw 不入库（CI 上不存在），语料 `jobs.jsonl` 才是随仓库走的。
    """
    jobs = ROOT / "data" / "processed" / "jobs.jsonl"
    if not jobs.exists():  # pragma: no cover - 只有代码没有语料时跳过
        pytest.skip("需要 data/processed/jobs.jsonl")
    rows = [json.loads(line) for line in
            jobs.read_text(encoding="utf-8").splitlines()[:8] if line.strip()]
    copy = tmp_path / "copy.csv"
    with copy.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["job_id", "company", "title", "jd_text"])
        for row in rows:  # 标题换成中性岗名，避免被标题过滤掉
            writer.writerow([row["job_id"], row["company"], "算法工程师", row["jd_clean"]])

    report = run([copy], jobs=jobs)
    pred, txt, ident = report["prediction"], report["text"], report["identity"]
    assert txt["overlap_count"] == len(rows)
    assert ident["collision_count"] == len(rows)
    assert pred["kept_new"] == 0
    assert pred["jobs_after"] == pred["jobs_before"]
    must = report["existing"]["must"]
    # 内部一致性：三项来源计数之和 == must 技能总数（= 项/岗 × 岗位数）
    assert sum(must["evidence"].values()) == pytest.approx(
        must["must_per_job"] * must["total_rows"], abs=1)


