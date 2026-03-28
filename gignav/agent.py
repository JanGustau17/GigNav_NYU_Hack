"""
GigNav ADK Agent - NYC Delivery Worker Equity Automator

This agent analyzes delivery worker earnings data from DCWP,
detects underpayment, and helps workers file wage complaints.
Uses Google ADK with Gemini for intelligent analysis.
"""

import json
import os
import pathlib

from google.adk import Agent
from google.adk.tools import FunctionTool
from google.genai.types import GenerateContentConfig, ThinkingConfig

# --- DCWP DATA ---

CURRENT_MIN_RATE = 22.13  # NYC minimum pay rate effective April 1, 2026

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

# Borough-level simulated data based on DCWP survey patterns
BOROUGH_DATA = {
    "Manhattan": {"avg_hourly_pay": 24.50, "avg_trips_per_hour": 2.8, "avg_tip_pct": 18},
    "Brooklyn": {"avg_hourly_pay": 22.80, "avg_trips_per_hour": 2.5, "avg_tip_pct": 16},
    "Queens": {"avg_hourly_pay": 21.90, "avg_trips_per_hour": 2.3, "avg_tip_pct": 15},
    "Bronx": {"avg_hourly_pay": 20.10, "avg_trips_per_hour": 2.0, "avg_tip_pct": 12},
    "Staten Island": {"avg_hourly_pay": 19.50, "avg_trips_per_hour": 1.8, "avg_tip_pct": 11},
}


# --- ADK TOOL FUNCTIONS ---

def check_wage_equity(borough: str, hours_worked: float, total_earned: float, total_pay: float = 0.0) -> dict:
    """Check if a delivery worker's pay meets NYC minimum requirements using DCWP data.

    Args:
        borough: NYC borough (Bronx, Brooklyn, Manhattan, Queens, Staten Island)
        hours_worked: Total hours worked in pay period
        total_earned: Total earnings (pay + tips)
        total_pay: Base pay excluding tips

    Returns:
        Analysis with status (UNDERPAID/COMPLIANT), rates, and recommendations.
    """
    effective_rate = total_earned / hours_worked if hours_worked > 0 else 0
    pay_rate = (total_pay / hours_worked) if total_pay and hours_worked > 0 else effective_rate

    latest = DCWP_QUARTERLY_DATA["Q2_2025"]
    city_avg_rate = latest["avg_earnings"] / latest["avg_hours"]

    borough_info = BOROUGH_DATA.get(borough, {})
    borough_avg = borough_info.get("avg_hourly_pay", city_avg_rate)

    is_underpaid = pay_rate < CURRENT_MIN_RATE
    underpayment = (CURRENT_MIN_RATE - pay_rate) * hours_worked if is_underpaid else 0

    result = {
        "status": "UNDERPAID" if is_underpaid else "COMPLIANT",
        "worker_effective_rate": round(effective_rate, 2),
        "worker_pay_rate": round(pay_rate, 2),
        "nyc_minimum_rate": CURRENT_MIN_RATE,
        "city_average_rate": round(city_avg_rate, 2),
        "borough": borough,
        "borough_average_rate": borough_avg,
        "underpayment_per_hour": round(max(0, CURRENT_MIN_RATE - pay_rate), 2),
        "total_underpayment": round(underpayment, 2),
        "hours_worked": hours_worked,
        "total_earned": total_earned,
        "total_workers_citywide": latest["total_workers"],
    }

    if is_underpaid:
        result["recommendation"] = (
            f"UNDERPAID: Worker in {borough} earned ${pay_rate:.2f}/hr, "
            f"which is ${CURRENT_MIN_RATE - pay_rate:.2f}/hr below the NYC minimum of ${CURRENT_MIN_RATE}/hr. "
            f"Total underpayment for this period: ${underpayment:.2f}. "
            f"Borough average is ${borough_avg}/hr. "
            f"Worker should file a wage complaint with NYC DCWP immediately."
        )
    else:
        result["recommendation"] = (
            f"COMPLIANT: Worker in {borough} earned ${pay_rate:.2f}/hr, "
            f"meeting the NYC minimum of ${CURRENT_MIN_RATE}/hr."
        )

    return result


def get_dcwp_quarterly_stats(quarter: str = "Q2_2025") -> dict:
    """Get DCWP quarterly statistics for delivery workers.

    Args:
        quarter: Quarter to query (e.g., Q2_2025, Q1_2024). Defaults to latest.

    Returns:
        Quarterly statistics including worker count, hours, earnings, pay, and tips.
    """
    data = DCWP_QUARTERLY_DATA.get(quarter)
    if not data:
        return {"error": f"No data for quarter {quarter}", "available_quarters": list(DCWP_QUARTERLY_DATA.keys())}

    hourly_rate = data["avg_earnings"] / data["avg_hours"]
    hourly_pay = data["avg_pay"] / data["avg_hours"]

    return {
        "quarter": quarter,
        "total_workers": data["total_workers"],
        "avg_weekly_hours": round(data["avg_hours"], 2),
        "avg_weekly_earnings": round(data["avg_earnings"], 2),
        "avg_weekly_pay": round(data["avg_pay"], 2),
        "avg_weekly_tips": round(data["avg_tips"], 2),
        "implied_hourly_earnings": round(hourly_rate, 2),
        "implied_hourly_pay": round(hourly_pay, 2),
        "nyc_minimum_rate": CURRENT_MIN_RATE,
        "minimum_met": hourly_pay >= CURRENT_MIN_RATE,
    }


def get_borough_comparison() -> dict:
    """Get borough-level comparison of delivery worker earnings.

    Returns:
        Borough-by-borough breakdown of average pay, trips, and tip percentages.
    """
    results = {}
    for borough, data in BOROUGH_DATA.items():
        results[borough] = {
            **data,
            "meets_minimum": data["avg_hourly_pay"] >= CURRENT_MIN_RATE,
            "gap_from_minimum": round(data["avg_hourly_pay"] - CURRENT_MIN_RATE, 2),
        }
    return {
        "nyc_minimum_rate": CURRENT_MIN_RATE,
        "boroughs": results,
        "analysis": "Bronx and Staten Island workers are most likely to be underpaid, "
                     "earning below the NYC minimum rate on average."
    }


def generate_complaint_text(
    worker_name: str,
    borough: str,
    hours_worked: float,
    total_pay: float,
    hourly_rate: float,
    underpayment: float,
    app_platform: str = "Unknown",
    pay_period: str = "Unknown",
) -> dict:
    """Generate detailed complaint text for a DCWP wage dispute filing.

    Args:
        worker_name: Full name of the worker
        borough: NYC borough
        hours_worked: Total hours worked
        total_pay: Total base pay received
        hourly_rate: Worker's effective hourly rate
        underpayment: Total underpayment amount
        app_platform: Delivery app name
        pay_period: Pay period description

    Returns:
        Formatted complaint text ready for submission.
    """
    complaint = (
        f"I, {worker_name}, am filing this complaint regarding underpayment by {app_platform} "
        f"for the pay period of {pay_period}. "
        f"During this period, I worked {hours_worked} hours in {borough} and received "
        f"${total_pay:.2f} in base pay, resulting in an effective hourly rate of ${hourly_rate:.2f}/hr. "
        f"This is ${CURRENT_MIN_RATE - hourly_rate:.2f}/hr below the NYC minimum delivery worker "
        f"pay rate of ${CURRENT_MIN_RATE}/hr (effective April 1, 2026, per NYC Administrative Code Section 20-1522). "
        f"The total underpayment for this period is ${underpayment:.2f}. "
        f"I request that DCWP investigate this violation and ensure I receive the full compensation owed."
    )
    return {
        "complaint_text": complaint,
        "key_facts": {
            "worker": worker_name,
            "borough": borough,
            "hours": hours_worked,
            "actual_rate": hourly_rate,
            "minimum_rate": CURRENT_MIN_RATE,
            "shortfall_per_hour": round(CURRENT_MIN_RATE - hourly_rate, 2),
            "total_owed": round(underpayment, 2),
        }
    }


# --- ADK AGENT DEFINITION ---

MODEL_ID = os.environ.get("MODEL_ID", "gemini-2.5-flash")
# Note: ADK uses GOOGLE_API_KEY env var automatically for authentication

root_agent = Agent(
    model=MODEL_ID,
    name="gignav",
    description="GigNav - NYC Delivery Worker Equity Automator. Analyzes earnings, detects underpayment using DCWP data, and helps file wage complaints.",
    instruction=f"""You are GigNav, an AI-powered worker advocacy agent for NYC delivery workers.

YOUR MISSION: Help delivery workers understand their earnings, check if they are being underpaid compared to NYC's minimum pay rate, and assist them in filing wage complaints.

KEY FACTS:
- NYC minimum pay rate for delivery workers: ${CURRENT_MIN_RATE}/hr (effective April 1, 2026)
- This rate applies to ALL hours: trip time + on-call time
- Under NYC Administrative Code Section 20-1522, delivery apps MUST pay at least the minimum rate
- Data source: DCWP quarterly delivery worker survey (73,850+ workers, 6 major apps)
- Covered apps: DoorDash, Grubhub, UberEats, Relay, FanTuan, HungryPanda

WORKFLOW:
1. When a worker provides their earnings info, use check_wage_equity to analyze their pay
2. Show them clear results: their rate vs the minimum, any underpayment amount
3. If underpaid, use generate_complaint_text to create their complaint
4. Provide borough comparisons and quarterly trends when relevant
5. Always be supportive and clear - these workers may not speak English as first language

IMPORTANT:
- Always ground your analysis in the actual DCWP data
- Be precise with dollar amounts and calculations
- Explain workers' rights clearly
- Filing a complaint is protected activity - apps cannot retaliate
""",
    tools=[
        check_wage_equity,
        get_dcwp_quarterly_stats,
        get_borough_comparison,
        generate_complaint_text,
    ],
)
