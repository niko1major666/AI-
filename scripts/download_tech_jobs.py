"""从 HF 下载真实科技岗位数据，映射到规范 CSV。

数据源：zalizedata/tech-job-postings-salary-dataset（含 company_name / title / salary / skills）
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    from datasets import load_dataset

    ds = load_dataset("zalizedata/tech-job-postings-salary-dataset", "S", streaming=True)
    split = list(ds.keys())[0]
    it = iter(ds[split])

    rows = []
    for i, row in enumerate(it):
        if i >= limit:
            break
        skills = row.get("skills") or []
        skills_str = ", ".join(str(s) for s in skills)
        jd_text = f"{row.get('title') or ''}. Department: {row.get('department') or ''}. Skills: {skills_str}"
        salary = ""
        if row.get("salary_min") and row.get("salary_max"):
            salary = (f"{row.get('salary_min')}-{row.get('salary_max')} "
                      f"{row.get('salary_currency') or ''}/{row.get('salary_period') or ''}")
        rows.append({
            "job_id": str(row.get("job_id") or f"tj_{i}"),
            "company": row.get("company_name") or "",
            "title": row.get("title") or "",
            "location": row.get("location_raw") or row.get("city") or "",
            "salary": salary.strip(),
            "experience": "",
            "education": "",
            "jd_text": jd_text,
        })

    import pandas as pd
    out = ROOT / "data" / "raw" / "tech_jobs.csv"
    pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")
    print(f"下载 {len(rows)} 条科技岗位 → {out}")


if __name__ == "__main__":
    main()
