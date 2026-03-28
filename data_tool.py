"""
GigNav Data Tool - Wage Equity Checker
Connects to BigQuery with DCWP delivery worker data to check if a worker is underpaid.
"""

import os
from google.cloud import bigquery

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "nyu-hack")
DATASET_ID = "gignav"
TABLE_ID = "worker_earnings"

# NYC Minimum Pay Rates for delivery workers
MIN_PAY_RATES = {
    "2024-04-01": 19.56,
    "2025-04-01": 21.44,
    "2026-04-01": 22.13,
}

CURRENT_MIN_RATE = 22.13  # Effective April 1, 2026

# Quarterly average data from DCWP reports (Q1 2022 - Q2 2025)
# Source: Restaurant-Delivery-App-Data-Quarterly.xlsx
DCWP_QUARTERLY_DATA = {
    "Q1_2022": {"total_workers": 116839, "avg_hours": 13.44, "avg_earnings": 180.48, "avg_pay": 95.40, "avg_tips": 85.08},
    "Q2_2022": {"total_workers": 115286, "avg_hours": 14.30, "avg_earnings": 173.36, "avg_pay": 88.55, "avg_tips": 84.81},
    "Q3_2022": {"total_workers": 107546, "avg_hours": 15.12, "avg_earnings": 171.30, "avg_pay": 85.78, "avg_tips": 85.52},
    "Q4_2022": {"total_workers": 110963, "avg_hours": 14.68, "avg_earnings": 186.83, "avg_pay": 95.14, "avg_tips": 91.69},
    "Q1_2023": {"total_workers": 111932, "avg_hours": 15.29, "avg_earnings": 187.60, "avg_pay": 93.27, "avg_tips": 94.33},
    "Q2_2023": {"total_workers": 109142, "avg_hours": 16.86, "avg_earnings": 189.13, "avg_pay": 92.75, "avg_tips": 96.38},
    "Q3_2023": {"total_workers": 106931, "avg_hours": 17.40, "avg_earnings": 182.82, "avg_pay": 88.15, "avg_tips": 94.67},
    "Q4_2023": {"total_workers": 111373, "avg_hours": 17.28, "avg_earnings": 217.35, "avg_pay": 131.23, "avg_tips": 86.12},
    "Q1_2024": {"total_workers": 102875, "avg_hours": 15.39, "avg_earnings": 292.32, "avg_pay": 251.93, "avg_tips": 40.39},
    "Q2_2024": {"total_workers": 86833, "avg_hours": 13.96, "avg_earnings": 313.80, "avg_pay": 270.01, "avg_tips": 43.79},
    "Q3_2024": {"total_workers": 77754, "avg_hours": 14.22, "avg_earnings": 318.08, "avg_pay": 274.23, "avg_tips": 43.85},
    "Q4_2024": {"total_workers": 74365, "avg_hours": 15.39, "avg_earnings": 349.04, "avg_pay": 299.09, "avg_tips": 49.95},
    "Q1_2025": {"total_workers": 82430, "avg_hours": 15.49, "avg_earnings": 348.05, "avg_pay": 298.89, "avg_tips": 49.16},
    "Q2_2025": {"total_workers": 73850, "avg_hours": 17.42, "avg_earnings": 418.66, "avg_pay": 366.51, "avg_tips": 52.15},
}


def get_latest_quarter_data():
    """Return the most recent DCWP quarterly data."""
    return DCWP_QUARTERLY_DATA["Q2_2025"]


def check_wage_equity(borough: str, hours_worked: float, total_earned: float, total_pay: float = None) -> dict:
    """
    Check if a delivery worker's pay meets NYC minimum requirements.

    Args:
        borough: NYC borough (Bronx, Brooklyn, Manhattan, Queens, Staten Island)
        hours_worked: Total hours worked in pay period
        total_earned: Total earnings (pay + tips)
        total_pay: Base pay excluding tips (if available)

    Returns:
        Dictionary with equity analysis results
    """
    effective_rate = total_earned / hours_worked if hours_worked > 0 else 0
    pay_rate = (total_pay / hours_worked) if total_pay and hours_worked > 0 else effective_rate

    latest = get_latest_quarter_data()
    city_avg_rate = latest["avg_earnings"] / latest["avg_hours"]  # ~$24.03/hr

    is_underpaid = pay_rate < CURRENT_MIN_RATE
    underpayment_amount = (CURRENT_MIN_RATE - pay_rate) * hours_worked if is_underpaid else 0

    result = {
        "status": "UNDERPAID" if is_underpaid else "COMPLIANT",
        "worker_effective_rate": round(effective_rate, 2),
        "worker_pay_rate": round(pay_rate, 2),
        "nyc_minimum_rate": CURRENT_MIN_RATE,
        "city_average_rate": round(city_avg_rate, 2),
        "underpayment_per_hour": round(max(0, CURRENT_MIN_RATE - pay_rate), 2),
        "total_underpayment": round(underpayment_amount, 2),
        "borough": borough,
        "hours_worked": hours_worked,
        "total_earned": total_earned,
        "total_workers_citywide": latest["total_workers"],
        "recommendation": "",
    }

    if is_underpaid:
        result["recommendation"] = (
            f"Worker in {borough} earned ${pay_rate:.2f}/hr, which is ${CURRENT_MIN_RATE - pay_rate:.2f}/hr "
            f"below the NYC minimum of ${CURRENT_MIN_RATE}/hr. Total underpayment: ${underpayment_amount:.2f}. "
            f"Worker should file a wage complaint with NYC DCWP."
        )
    else:
        result["recommendation"] = (
            f"Worker in {borough} earned ${pay_rate:.2f}/hr, meeting the NYC minimum of ${CURRENT_MIN_RATE}/hr."
        )

    return result


def upload_to_bigquery():
    """Upload DCWP quarterly data to BigQuery for the demo."""
    client = bigquery.Client(project=PROJECT_ID)

    # Create dataset if not exists
    dataset_ref = f"{PROJECT_ID}.{DATASET_ID}"
    try:
        client.get_dataset(dataset_ref)
    except Exception:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        client.create_dataset(dataset, exists_ok=True)

    # Create table schema
    schema = [
        bigquery.SchemaField("quarter", "STRING"),
        bigquery.SchemaField("total_workers", "INTEGER"),
        bigquery.SchemaField("avg_hours", "FLOAT"),
        bigquery.SchemaField("avg_earnings", "FLOAT"),
        bigquery.SchemaField("avg_pay", "FLOAT"),
        bigquery.SchemaField("avg_tips", "FLOAT"),
    ]

    table_ref = f"{dataset_ref}.{TABLE_ID}"

    rows = []
    for quarter, data in DCWP_QUARTERLY_DATA.items():
        rows.append({
            "quarter": quarter,
            "total_workers": data["total_workers"],
            "avg_hours": data["avg_hours"],
            "avg_earnings": data["avg_earnings"],
            "avg_pay": data["avg_pay"],
            "avg_tips": data["avg_tips"],
        })

    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition="WRITE_TRUNCATE",
    )

    job = client.load_table_from_json(rows, table_ref, job_config=job_config)
    job.result()
    print(f"Loaded {len(rows)} rows into {table_ref}")
    return table_ref


def query_bigquery_avg(quarter: str = "Q2_2025") -> dict:
    """Query BigQuery for average earnings data."""
    client = bigquery.Client(project=PROJECT_ID)
    query = f"""
        SELECT avg_hours, avg_earnings, avg_pay, avg_tips, total_workers
        FROM `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`
        WHERE quarter = '{quarter}'
    """
    result = client.query(query).result()
    for row in result:
        return dict(row)
    return {}


if __name__ == "__main__":
    # Demo: Check wage equity for our mock worker
    print("=== GigNav Wage Equity Check ===\n")
    result = check_wage_equity(
        borough="Bronx",
        hours_worked=40,
        total_earned=568.00,
        total_pay=412.00,
    )
    for k, v in result.items():
        print(f"  {k}: {v}")

    print("\n=== Uploading to BigQuery ===")
    try:
        upload_to_bigquery()
        print("BigQuery upload successful!")
        print("\n=== Querying BigQuery ===")
        bq_result = query_bigquery_avg()
        print(f"  BigQuery result: {bq_result}")
    except Exception as e:
        print(f"  BigQuery not available (using local data): {e}")
