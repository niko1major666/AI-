import json

import yaml

from src.data.job_filter import is_offtopic_title, normalize_title


def test_normalize_title_strips_separators():
    assert normalize_title("AI-建筑 智能化（工程师）") == "ai建筑智能化工程师"
    assert normalize_title(None) == ""


def test_offtopic_titles():
    for title in ["暖通工程师", "包装结构工程师-手机", "电池系统结构工程师-2027届",
                  "建筑设计管理", "土木工程师", "道路桥梁设计师", "施工员",
                  "工程造价", "岩土工程勘察", "市政给排水工程师", "工程测量员",
                  "消防工程施工图设计师", "结构工程师（土建）"]:
        assert is_offtopic_title(title) is True, title


def test_ai_titles_kept():
    for title in ["AI 算法工程师", "大模型算法工程师", "机器学习工程师",
                  "NLP 算法（智能客服）", "建筑智能化 AI 产品经理",
                  "模型结构优化工程师", "数据结构工程师", "推荐系统工程师",
                  "建筑工程 AI 解决方案架构师", "CV 算法工程师",
                  "Agent 基础设施工程师", "dots-模型结构算法工程师"]:
        assert is_offtopic_title(title) is False, title


def test_empty_title_not_filtered():
    assert is_offtopic_title("") is False
    assert is_offtopic_title(None) is False
    assert is_offtopic_title("   ") is False


def test_custom_keywords_override_default():
    assert is_offtopic_title("化工工艺工程师", exclude_keywords=["化工"]) is True
    # 自定义黑名单替换默认词表：暖通不再被剔除
    assert is_offtopic_title("暖通工程师", exclude_keywords=["化工"]) is False
    # 自定义黑名单 + 默认白名单：含 AI 信号仍保留
    assert is_offtopic_title("化工 AI 算法工程师", exclude_keywords=["化工"]) is False


def test_keep_keywords_override_default():
    assert is_offtopic_title("暖通工程师", keep_keywords=["暖通"]) is False
    # 空白名单 = 不启用白名单保护
    assert is_offtopic_title("建筑 AI 算法工程师", keep_keywords=[]) is True


def test_build_dataset_applies_title_filter(tmp_path):
    """管线接入：开启 title_filter 后，工程类标题应在构建阶段被剔除并计入 stats。"""
    from src.data import build_dataset

    csv = tmp_path / "jobs.csv"
    csv.write_text(
        "job_id,company,title,location,salary,experience,education,jd_text\n"
        "a1,某公司,暖通工程师,北京,20-30K,3-5年,本科,负责暖通空调系统设计与施工图审核工作，熟悉CAD。\n"
        "a2,某公司,AI 算法工程师,北京,40-70K,3-5年,硕士,负责大模型算法研发，熟悉Python与PyTorch。\n"
        "a3,某公司,建筑设计管理,上海,20-30K,5-10年,本科,负责建筑设计项目管理与施工图进度把控工作。\n",
        encoding="utf-8",
    )
    cfg = {
        "source": {"type": "local_csv", "path": str(csv), "job_prefix": "jd"},
        "column_mapping": {"job_id": "job_id", "company": "company", "title": "title",
                           "location": "location", "salary": "salary",
                           "experience": "experience", "education": "education",
                           "jd_text": "jd_text"},
        "cleaning": {"min_jd_chars": 10, "normalize_company": True,
                     "title_filter": {"enabled": True}},
        "output": {"jobs_jsonl": "data/processed/jobs.jsonl"},
    }
    cfg_path = tmp_path / "dataset.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")

    stats = build_dataset.build(cfg_path, out_dir=tmp_path / "out")
    assert stats["raw_rows"] == 3
    assert stats["dropped_offtopic"] == 2
    assert "暖通工程师" in stats["offtopic_samples"]

    jobs = [json.loads(x) for x in (tmp_path / "out" / "jobs.jsonl")
            .read_text(encoding="utf-8").splitlines()]
    assert [j["title"] for j in jobs] == ["AI 算法工程师"]


def test_build_dataset_title_filter_disabled(tmp_path):
    """未配置 title_filter 时不剔除任何岗位，stats 记 0。"""
    from src.data import build_dataset

    csv = tmp_path / "jobs.csv"
    csv.write_text(
        "job_id,company,title,location,salary,experience,education,jd_text\n"
        "b1,某公司,暖通工程师,北京,20-30K,3-5年,本科,负责暖通空调系统设计与施工图审核工作，熟悉CAD。\n",
        encoding="utf-8",
    )
    cfg = {
        "source": {"type": "local_csv", "path": str(csv), "job_prefix": "jd"},
        "column_mapping": {"job_id": "job_id", "company": "company", "title": "title",
                           "location": "location", "salary": "salary",
                           "experience": "experience", "education": "education",
                           "jd_text": "jd_text"},
        "cleaning": {"min_jd_chars": 10, "normalize_company": True},
        "output": {"jobs_jsonl": "data/processed/jobs.jsonl"},
    }
    cfg_path = tmp_path / "dataset.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")

    stats = build_dataset.build(cfg_path, out_dir=tmp_path / "out2")
    assert stats["dropped_offtopic"] == 0
    assert stats["cleaned_rows"] == 1
