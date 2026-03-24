"""
Generate employee dimension data for Tales & Timber.

Output: employees.parquet

Scale targets
─────────────
  NUM_EMPLOYEES = 15,000   (set in config via scale profile)
  NUM_STORES    =    500
  Employee ID   = E-{n:06d}
  Store    ID   = S-{n:04d}

Uses vectorised NumPy for all bulk column generation.  Faker is called
sequentially for names (unavoidable) but every other column is built as
a full-length array in one shot.
"""

import os

import numpy as np
import pandas as pd
from faker import Faker

import config as cfg

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

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

# Titles that sit at HQ regardless of department
_HQ_TITLES = frozenset({
    "CMO", "CTO", "CFO", "CHRO",
    "VP Operations", "VP Supply Chain",
    "Regional Sales Director",
})

# Departments that are entirely HQ-based
_HQ_DEPTS = frozenset({"IT", "Finance", "HR"})

# Junior-heavy weight pattern applied to the 4-tier title ladder
_TITLE_WEIGHTS = np.array([0.50, 0.25, 0.18, 0.07])


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def generate_employees() -> pd.DataFrame:
    """Build the employee dimension using vectorised NumPy where possible."""
    rng = np.random.default_rng(cfg.SEED)
    fake = Faker()
    Faker.seed(cfg.SEED)

    n = cfg.NUM_EMPLOYEES  # 15 000
    depts = np.array(cfg.DEPARTMENTS)
    emp_nums = np.arange(1, n + 1)

    # ── Department (vectorised) ───────────────────────────────────────────
    dept_idx = rng.integers(0, len(depts), size=n)
    departments = depts[dept_idx]

    # ── Title — vectorised per department ─────────────────────────────────
    titles = np.empty(n, dtype=object)
    for d_i, dept in enumerate(depts):
        mask = dept_idx == d_i
        count = int(mask.sum())
        if count == 0:
            continue
        dept_titles = TITLES_BY_DEPT[dept]
        w = _TITLE_WEIGHTS[: len(dept_titles)].copy()
        w /= w.sum()
        titles[mask] = rng.choice(dept_titles, size=count, p=w)

    # ── Salary (vectorised) ───────────────────────────────────────────────
    sal_lo = np.array([SALARY_RANGES[t][0] for t in titles], dtype=np.float64)
    sal_hi = np.array([SALARY_RANGES[t][1] for t in titles], dtype=np.float64)
    salaries = np.round(rng.uniform(sal_lo, sal_hi), 2)

    # ── HQ flag → store assignment (vectorised) ──────────────────────────
    is_hq = (
        np.isin(departments, list(_HQ_DEPTS))
        | np.isin(titles, list(_HQ_TITLES))
    )
    store_nums = rng.integers(1, cfg.NUM_STORES + 1, size=n)
    store_ids = np.array(
        [cfg.store_id(int(s)) for s in store_nums], dtype=object,
    )
    store_ids[is_hq] = None

    # ── Hire date (vectorised) ────────────────────────────────────────────
    start_ts = pd.Timestamp(cfg.START_DATE)
    days_offset = rng.integers(0, 3650, size=n)
    hire_dates = start_ts - pd.to_timedelta(days_offset, unit="D")

    # ── Performance rating (vectorised) ───────────────────────────────────
    perf_ratings = rng.choice(
        [1, 2, 3, 4, 5],
        size=n,
        p=[0.05, 0.10, 0.40, 0.30, 0.15],
    )

    # ── Manager hierarchy (vectorised) ────────────────────────────────────
    # Top-level titles and the first 10 employees are hierarchy roots.
    is_root = np.isin(titles, list(_HQ_TITLES)) | (emp_nums <= 10)

    # Each non-root employee's manager is a random employee from the first
    # quarter of employees up to that employee's own position — keeps the
    # org chart realistic (managers have lower IDs).
    mgr_upper = np.maximum(2, emp_nums // 4)          # exclusive upper bound
    mgr_nums = rng.integers(np.ones(n, dtype=np.intp), mgr_upper)
    manager_ids = np.array(
        [cfg.employee_id(int(m)) for m in mgr_nums], dtype=object,
    )
    manager_ids[is_root] = None

    # ── Names & email (Faker is inherently sequential) ────────────────────
    first_names = np.array([fake.first_name() for _ in range(n)], dtype=object)
    last_names = np.array([fake.last_name() for _ in range(n)], dtype=object)
    emails = np.array(
        [
            f"{fn.lower()}.{ln.lower()}{i}@talesandtimber.com"
            for i, fn, ln in zip(emp_nums, first_names, last_names)
        ],
        dtype=object,
    )

    # ── Active flag (vectorised) ──────────────────────────────────────────
    is_active = rng.random(n) < 0.93

    # ── Assemble DataFrame ────────────────────────────────────────────────
    return pd.DataFrame(
        {
            "employee_id": [cfg.employee_id(int(i)) for i in emp_nums],
            "first_name": first_names,
            "last_name": last_names,
            "email": emails,
            "department": departments,
            "title": titles,
            "store_id": store_ids,
            "hire_date": hire_dates,
            "salary": salaries,
            "performance_rating": perf_ratings,
            "manager_id": manager_ids,
            "is_active": is_active,
        }
    )


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def main() -> None:
    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
    print("Generating employees …")
    df = generate_employees()
    path = os.path.join(cfg.OUTPUT_DIR, "employees.parquet")
    df.to_parquet(path, index=False, engine="pyarrow", compression="snappy")
    print(f"  ✓ {len(df):,} employees → {path}")


if __name__ == "__main__":
    main()
