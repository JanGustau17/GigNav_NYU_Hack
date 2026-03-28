"""
GigNav Navigator Agent (A2A) - Browser Automation Service
This agent handles screen reading and form filling via Computer Use.
"""

import os
from google.adk import Agent


def read_earnings_screen(
    worker_name: str, borough: str, hours_worked: float,
    total_pay: float, total_tips: float, hourly_rate: float,
    worker_id: str = "", vehicle_type: str = "", app_platform: str = "",
) -> dict:
    """Extract and validate earnings data from a delivery worker's screen.

    Args:
        worker_name: Worker's full name
        borough: NYC borough
        hours_worked: Total hours in pay period
        total_pay: Base pay excluding tips
        total_tips: Total tips received
        hourly_rate: Effective hourly rate shown
        worker_id: Worker's platform ID
        vehicle_type: Vehicle used (E-Bike, Car, etc.)
        app_platform: Delivery app name

    Returns:
        Validated and structured earnings data.
    """
    total_earned = total_pay + total_tips
    calculated_rate = total_earned / hours_worked if hours_worked > 0 else 0

    return {
        "worker_name": worker_name,
        "borough": borough,
        "hours_worked": hours_worked,
        "total_pay": total_pay,
        "total_tips": total_tips,
        "total_earned": total_earned,
        "displayed_hourly_rate": hourly_rate,
        "calculated_hourly_rate": round(calculated_rate, 2),
        "worker_id": worker_id,
        "vehicle_type": vehicle_type,
        "app_platform": app_platform,
        "rate_matches": abs(calculated_rate - hourly_rate) < 0.5,
        "status": "extracted",
    }


def prepare_complaint_form_data(
    worker_name: str, worker_id: str, email: str, phone: str,
    borough: str, app_platform: str, vehicle_type: str,
    period_start: str, period_end: str, hours_worked: float,
    total_pay: float, total_tips: float, hourly_rate: float,
    complaint_description: str,
) -> dict:
    """Prepare all data needed to fill a DCWP complaint form.

    Args:
        worker_name: Full name
        worker_id: Platform worker ID
        email: Contact email
        phone: Contact phone
        borough: NYC borough
        app_platform: Delivery app
        vehicle_type: Vehicle type
        period_start: Pay period start (YYYY-MM-DD)
        period_end: Pay period end (YYYY-MM-DD)
        hours_worked: Total hours
        total_pay: Base pay
        total_tips: Tips received
        hourly_rate: Effective rate
        complaint_description: Detailed complaint text

    Returns:
        Structured form data ready for auto-fill.
    """
    return {
        "form_fields": {
            "fullName": worker_name,
            "workerId": worker_id,
            "email": email,
            "phone": phone,
            "borough": borough,
            "appPlatform": app_platform,
            "vehicleType": vehicle_type,
            "periodStart": period_start,
            "periodEnd": period_end,
            "hoursWorked": str(hours_worked),
            "totalPay": f"${total_pay:.2f}",
            "totalTips": f"${total_tips:.2f}",
            "hourlyRate": f"${hourly_rate:.2f}",
            "description": complaint_description,
        },
        "status": "ready_to_fill",
    }


root_agent = Agent(
    model=os.environ.get("MODEL_ID", "gemini-2.5-flash"),
    name="navigator_agent",
    description="Browser Navigator Agent - reads delivery worker earnings screens and prepares complaint form data for auto-filling.",
    instruction="""You are the GigNav Navigator Agent, specialized in reading delivery worker
earnings screens and preparing data for complaint form submission.
When given an image of an earnings screen, extract all relevant data accurately.
When asked to prepare form data, structure it precisely for the DCWP complaint form.""",
    tools=[
        read_earnings_screen,
        prepare_complaint_form_data,
    ],
)
