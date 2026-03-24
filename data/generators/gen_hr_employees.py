"""
Generate employee dimension data for Contoso Global Retail.

Output: employees.parquet
"""

import os

import numpy as np
import pandas as pd
from faker import Faker

import config as cfg

TITLES_BY_DEPT = {
    "Sales": ["Sales Associate", "Sales Lead", "Sales Manager", "Regional Sales Director"],
    "Operations": ["Operations Analyst", "Operations Manager", "Logistics Coordinator", "VP Operations"],
    "Marketing": ["Marketing Specialist", "Campaign Manager", "Brand Manager", "CMO"],
    "IT": ["Software Engineer", "Data Engineer", "IT Manager", "CTO"],
    "Finance": ["Financial Analyst", "Accountant", "Finance Manager", "CFO"],
    "HR": ["HR Coordinator", "Recruiter", "HR Manager", "CHRO"],
    "Supply Chain": ["Supply Chain Analyst", "Procurement Specialist", "SC Manager", "VP Supply Chain"],
}

SALARY_RANGES = {
    "Sales Associate": (30_000, 50_000),
    "Sales Lead": (45_000, 65_000),
    "Sales Manager": (60_000, 90_000),
    "Regional Sales Director": (90_000, 150_000),
    "Operations Analyst": (40_000, 60_000),
    "Operations Manager": (65_000, 100_000),
    "Logistics Coordinator": (35_000, 55_000),
    "VP Operations": (110_000, 180_000),
    "Marketing Specialist": (40_000, 65_000),
    "Campaign Manager": (55_000, 85_000),
    "Brand Manager": (70_000, 110_000),
    "CMO": (130_000, 220_000),
    "Software Engineer": (70_000, 130_000),
    "Data Engineer": (75_000, 135_000),
    "IT Manager": (90_000, 140_000),
    "CTO": (150_000, 250_000),
    "Financial Analyst": (50_000, 80_000),
    "Accountant": (45_000, 70_000),
    "Finance Manager": (80_000, 120_000),
    "CFO": (140_000, 240_000),
    "HR Coordinator": (35_000, 55_000),
    "Recruiter": (40_000, 65_000),
    "HR Manager": (70_000, 100_000),
    "CHRO": (120_000, 200_000),
    "Supply Chain Analyst": (45_000, 70_000),
    "Procurement Specialist": (50_000, 75_000),
    "SC Manager": (75_000, 110_000),
    "VP Supply Chain": (110_000, 180_000),
}


def generate_employees() -> pd.DataFrame:
    rng = np.random.default_rng(cfg.SEED)
    fake = Faker()
    Faker.seed(cfg.SEED)

    rows: list[dict] = []
    for i in range(1, cfg.NUM_EMPLOYEES + 1):
        dept = rng.choice(cfg.DEPARTMENTS)
        titles = TITLES_BY_DEPT[dept]
        # Weighted toward junior titles
        title_weights = np.array([0.50, 0.25, 0.18, 0.07][: len(titles)])
        title_weights = title_weights / title_weights.sum()
        title = rng.choice(titles, p=title_weights)

        sal_lo, sal_hi = SALARY_RANGES[title]
        salary = round(float(rng.uniform(sal_lo, sal_hi)), 2)

        # HQ staff (IT, Finance, HR, Marketing top-level) have no store
        is_hq = dept in ("IT", "Finance", "HR") or title in ("CMO", "VP Operations", "VP Supply Chain", "CTO", "CFO", "CHRO", "Regional Sales Director")
        store = None if is_hq else cfg.store_id(int(rng.integers(1, cfg.NUM_STORES + 1)))

        hire_date = cfg.START_DATE - pd.Timedelta(
            days=int(rng.integers(0, 3650))
        )

        perf = int(rng.choice([1, 2, 3, 4, 5], p=[0.05, 0.10, 0.40, 0.30, 0.15]))

        # Manager hierarchy: top-level titles manage themselves (root), others
        # get a random earlier employee as manager
        if i <= 10 or title in ("CTO", "CFO", "CHRO", "CMO", "VP Operations", "VP Supply Chain", "Regional Sales Director"):
            manager = None
        else:
            manager = cfg.employee_id(int(rng.integers(1, max(2, i // 4))))

        rows.append(
            {
                "employee_id": cfg.employee_id(i),
                "first_name": fake.first_name(),
                "last_name": fake.last_name(),
                "email": f"{fake.first_name().lower()}.{fake.last_name().lower()}{i}@contoso.com",
                "department": dept,
                "title": title,
                "store_id": store,
                "hire_date": hire_date,
                "salary": salary,
                "performance_rating": perf,
                "manager_id": manager,
                "is_active": bool(rng.random() < 0.93),
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
    print("Generating employees …")
    df = generate_employees()
    path = os.path.join(cfg.OUTPUT_DIR, "employees.parquet")
    df.to_parquet(path, index=False, engine="pyarrow")
    print(f"  ✓ {len(df):,} employees → {path}")


if __name__ == "__main__":
    main()
