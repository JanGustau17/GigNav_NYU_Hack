#  Copyright 2025 Google LLC
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import asyncio
import json
import logging
import os
import pathlib

from google import genai
from google.genai.types import (
    ComputerUse,
    Content,
    Environment,
    FunctionDeclaration,
    FunctionResponse,
    FunctionResponseBlob,
    GenerateContentConfig,
    Part,
    Schema,
    ThinkingConfig,
    Tool,
    FinishReason,
)
from playwright.async_api import Page, async_playwright

from data_tool import check_wage_equity, DCWP_QUARTERLY_DATA, CURRENT_MIN_RATE

logging.getLogger("google_genai._common").setLevel(logging.ERROR)

# --- CONFIGURATION ---
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "nyu-hack")
LOCATION = os.environ.get("GOOGLE_LOCATION", "global")
API_KEY = os.environ.get("GOOGLE_API_KEY", "")
MODEL_ID = os.environ.get("MODEL_ID", "gemini-3-flash-preview")

# Resolve mock page paths
BASE_DIR = pathlib.Path(__file__).parent
EARNINGS_PAGE = (BASE_DIR / "mock_earnings.html").resolve().as_uri()
FORM_PAGE = (BASE_DIR / "mock_form.html").resolve().as_uri()

# --- GIGNAV SYSTEM PROMPT ---
GIGNAV_SYSTEM_PROMPT = f"""You are GigNav, an autonomous worker advocacy agent built for NYC delivery workers.

YOUR MISSION: Monitor delivery worker earnings screens, detect underpayment, and automatically navigate to and fill out NYC DCWP wage complaint forms on behalf of workers.

CONTEXT:
- NYC minimum pay rate for delivery workers: ${CURRENT_MIN_RATE}/hr (effective April 1, 2026)
- This rate applies to ALL hours: trip time + on-call time
- Under NYC Administrative Code 20-1522, delivery apps must pay at least the minimum rate
- Source data: DCWP quarterly delivery worker survey data

WORKFLOW:
1. OBSERVE the earnings dashboard screen carefully. Extract: worker name, borough, hours worked, total pay, total tips, effective hourly rate.
2. Use the check_wage_equity tool to verify if the worker is being underpaid based on DCWP data.
3. If UNDERPAID: Navigate to the complaint form page and fill in ALL fields with the worker's information.
4. Fill in the complaint description with specific details about the underpayment amount and rate differential.
5. Submit the form.

IMPORTANT RULES:
- Read the screen carefully before acting. Extract exact numbers.
- When filling forms, click on each field first, then type the value.
- Be precise with dates, amounts, and calculations.
- Always explain what you're doing as you go.
"""

# --- CUSTOM TOOL DEFINITIONS ---
check_wage_equity_tool = FunctionDeclaration(
    name="check_wage_equity",
    description="Check if a delivery worker's pay meets NYC minimum requirements using DCWP data. Returns analysis with underpayment amount if applicable.",
    parameters=Schema(
        type="OBJECT",
        properties={
            "borough": Schema(type="STRING", description="NYC borough: Bronx, Brooklyn, Manhattan, Queens, or Staten Island"),
            "hours_worked": Schema(type="NUMBER", description="Total hours worked in the pay period"),
            "total_earned": Schema(type="NUMBER", description="Total earnings including tips"),
            "total_pay": Schema(type="NUMBER", description="Base pay excluding tips"),
        },
        required=["borough", "hours_worked", "total_earned"],
    ),
)


# --- HELPER FUNCTIONS ---

def normalize_x(x: int, screen_width: int) -> int:
    return int(x / 1000 * screen_width)


def normalize_y(y: int, screen_height: int) -> int:
    return int(y / 1000 * screen_height)


async def execute_function_calls(
    response, page: Page, screen_width: int, screen_height: int
) -> tuple[str, list[tuple[str, str, bool]]]:
    await asyncio.sleep(0.1)

    function_calls = [
        part.function_call
        for part in response.candidates[0].content.parts
        if hasattr(part, "function_call") and part.function_call
    ]

    thoughts = [
        part.text
        for part in response.candidates[0].content.parts
        if hasattr(part, "text") and part.text
    ]

    if thoughts:
        print(f"🤔 GigNav Reasoning: {' '.join(thoughts)}")

    if not function_calls:
        return "NO_ACTION", []

    results = []
    for function_call in function_calls:
        result = None
        safety_acknowledged = False

        safety_decision = function_call.args.get("safety_decision")
        if (
            safety_decision
            and safety_decision.get("decision") == "require_confirmation"
        ):
            print(f"\n⚠️ SAFETY PROMPT: {safety_decision.get('explanation')}")
            user_input = input(
                f"Allow GigNav to execute '{function_call.name}'? (y/n): "
            )

            if user_input.strip().lower() not in ["y", "yes"]:
                print("🚫 Action denied by user.")
                results.append((function_call.name, "user_denied", False))
                continue

            print("✅ Action approved.")
            safety_acknowledged = True

        print(f"⚡ GigNav Action: {function_call.name}")

        try:
            # Handle our custom tool
            if function_call.name == "check_wage_equity":
                equity_result = check_wage_equity(
                    borough=function_call.args.get("borough", "Unknown"),
                    hours_worked=float(function_call.args.get("hours_worked", 0)),
                    total_earned=float(function_call.args.get("total_earned", 0)),
                    total_pay=float(function_call.args.get("total_pay", 0)) if function_call.args.get("total_pay") else None,
                )
                print(f"📊 Wage Equity Result: {equity_result['status']}")
                print(f"   Rate: ${equity_result['worker_pay_rate']}/hr vs minimum ${CURRENT_MIN_RATE}/hr")
                if equity_result['status'] == 'UNDERPAID':
                    print(f"   💰 Underpayment: ${equity_result['total_underpayment']}")
                result = json.dumps(equity_result)

            # Browser actions
            elif function_call.name == "open_web_browser":
                result = "success"
            elif function_call.name == "navigate":
                await page.goto(function_call.args["url"])
                result = "success"
            elif function_call.name == "click_at":
                actual_x = normalize_x(function_call.args["x"], screen_width)
                actual_y = normalize_y(function_call.args["y"], screen_height)
                await page.mouse.click(actual_x, actual_y)
                result = "success"
            elif function_call.name == "type_text_at":
                text_to_type = function_call.args["text"]
                print(f'   📝 Typing: "{text_to_type}"')
                actual_x = normalize_x(function_call.args["x"], screen_width)
                actual_y = normalize_y(function_call.args["y"], screen_height)
                await page.mouse.click(actual_x, actual_y)
                await asyncio.sleep(0.1)
                await page.keyboard.type(text_to_type)
                if function_call.args.get("press_enter", False):
                    await page.keyboard.press("Enter")
                result = "success"
            elif function_call.name == "scroll":
                direction = function_call.args.get("direction", "down")
                amount = function_call.args.get("amount", 3)
                delta = -amount * 100 if direction == "up" else amount * 100
                await page.mouse.wheel(0, delta)
                result = "success"
            elif function_call.name == "select_option":
                # Handle dropdown selection
                actual_x = normalize_x(function_call.args["x"], screen_width)
                actual_y = normalize_y(function_call.args["y"], screen_height)
                await page.mouse.click(actual_x, actual_y)
                await asyncio.sleep(0.2)
                value = function_call.args.get("value", "")
                await page.keyboard.type(value)
                await page.keyboard.press("Enter")
                result = "success"
            else:
                result = "unknown_function"
        except Exception as e:
            print(f"❗️ Error executing {function_call.name}: {e}")
            result = f"error: {e!s}"

        results.append((function_call.name, result, safety_acknowledged))

    return "CONTINUE", results


# --- THE AGENT LOOP ---

async def agent_loop(initial_prompt: str, max_turns: int = 30) -> None:
    if not API_KEY and not PROJECT_ID:
        raise ValueError("Set GOOGLE_API_KEY or GOOGLE_CLOUD_PROJECT environment variable.")

    if API_KEY:
        client = genai.Client(api_key=API_KEY)
    else:
        client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            sw, sh = 960, 1080
            await page.set_viewport_size({"width": sw, "height": sh})

            # Start on the earnings dashboard
            await page.goto(EARNINGS_PAGE)
            await asyncio.sleep(1)

            print(f"\n{'='*60}")
            print(f"🚀 GigNav - NYC Delivery Worker Equity Automator")
            print(f"{'='*60}")
            print(f"📊 Current NYC Minimum Rate: ${CURRENT_MIN_RATE}/hr")
            print(f"🌐 Earnings Page: {EARNINGS_PAGE}")
            print(f"📋 Complaint Form: {FORM_PAGE}")
            print(f"{'='*60}\n")

            # Configure tools: Computer Use + our custom wage equity tool
            config_kwargs = {
                "system_instruction": GIGNAV_SYSTEM_PROMPT,
                "tools": [
                    Tool(
                        computer_use=ComputerUse(
                            environment=Environment.ENVIRONMENT_BROWSER,
                            excluded_predefined_functions=["drag_and_drop"],
                        )
                    ),
                    Tool(function_declarations=[check_wage_equity_tool]),
                ],
            }

            try:
                model_version = float(MODEL_ID.split("-")[1])
            except (IndexError, ValueError):
                model_version = 3.0
            if model_version >= 3:
                config_kwargs["thinking_config"] = ThinkingConfig(include_thoughts=True)

            config = GenerateContentConfig(**config_kwargs)

            screenshot = await page.screenshot()
            contents = [
                Content(
                    role="user",
                    parts=[
                        Part(text=initial_prompt),
                        Part.from_bytes(data=screenshot, mime_type="image/png"),
                    ],
                )
            ]

            for turn in range(max_turns):
                print(f"\n--- 🔁 Turn {turn + 1} ---")
                print(f"[URL] {page.url}")

                # Retry with backoff for rate limits
                response = None
                for retry in range(5):
                    try:
                        response = client.models.generate_content(
                            model=MODEL_ID, contents=contents, config=config
                        )
                        break
                    except Exception as e:
                        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or "503" in str(e):
                            wait_time = 20 * (retry + 1)
                            print(f"⏳ Rate limited. Waiting {wait_time}s... (attempt {retry+1}/5)")
                            await asyncio.sleep(wait_time)
                        else:
                            raise

                if not response or not response.candidates:
                    print("❗️ No candidates returned. Stopping.")
                    break

                if response.candidates[0].finish_reason == FinishReason.SAFETY:
                    print(f"🛑 SAFETY BLOCK: {response.candidates[0].safety_ratings}")
                    break

                contents.append(response.candidates[0].content)

                active_function_calls = [
                    part.function_call
                    for part in response.candidates[0].content.parts
                    if hasattr(part, "function_call") and part.function_call
                ]

                if not active_function_calls:
                    final_text = "".join(
                        part.text
                        for part in response.candidates[0].content.parts
                        if hasattr(part, "text") and part.text is not None
                    )
                    if final_text:
                        print(f"\n✅ GigNav Complete: {final_text}")
                        break

                status, execution_results = await execute_function_calls(
                    response, page, sw, sh
                )

                if status == "NO_ACTION":
                    continue

                function_response_parts = []
                for name, result, safety_acknowledged in execution_results:
                    screenshot = await page.screenshot()
                    current_url = page.url

                    response_payload = {"url": current_url}

                    # For our custom tool, include the data result
                    if name == "check_wage_equity":
                        try:
                            response_payload["data"] = json.loads(result)
                        except (json.JSONDecodeError, TypeError):
                            response_payload["result"] = result

                    if result == "user_denied":
                        response_payload["error"] = "user_denied"
                    elif safety_acknowledged:
                        response_payload["safety_acknowledgement"] = True

                    function_response_parts.append(
                        Part(
                            function_response=FunctionResponse(
                                name=name,
                                response=response_payload,
                                parts=[
                                    Part(
                                        inline_data=FunctionResponseBlob(
                                            mime_type="image/png", data=screenshot
                                        )
                                    )
                                ],
                            )
                        )
                    )

                contents.append(Content(role="user", parts=function_response_parts))
                print(f"📝 History: {len(contents)} messages")

    finally:
        if browser:
            await browser.close()
            print("\n--- Browser closed. ---")


# --- SCRIPT ENTRY POINT ---
if __name__ == "__main__":
    prompt = (
        "You are looking at a delivery worker's earnings dashboard. "
        "Please do the following:\n"
        "1. Read the screen carefully and extract the worker's name, borough, hours worked, total pay, total tips, and effective hourly rate.\n"
        "2. Use the check_wage_equity tool to verify if they are being underpaid based on NYC DCWP data.\n"
        "3. If the worker IS underpaid, navigate to the complaint form at: " + FORM_PAGE + "\n"
        "4. Fill in ALL fields of the complaint form with the worker's information from the earnings dashboard.\n"
        "   - Full Name: from the dashboard\n"
        "   - Worker ID: from the dashboard\n"
        "   - Email: use carlos.rivera@email.com\n"
        "   - Phone: use (718) 555-0142\n"
        "   - Borough: from the dashboard\n"
        "   - App Platform: select the closest match to the app shown\n"
        "   - Vehicle Type: from the dashboard\n"
        "   - Pay Period Start: 2026-03-17\n"
        "   - Pay Period End: 2026-03-23\n"
        "   - Hours Worked: from the dashboard\n"
        "   - Total Pay: from the dashboard (base pay only)\n"
        "   - Total Tips: from the dashboard\n"
        "   - Effective Hourly Rate: from the dashboard\n"
        "   - Description: Write a detailed description of the underpayment including the rate differential and total amount owed.\n"
        "5. Click the SUBMIT COMPLAINT button.\n"
    )

    asyncio.run(agent_loop(prompt))
