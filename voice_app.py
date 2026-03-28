"""
GigNav Voice App - Real-time voice interface using Gemini Live API
Supports Speech-to-Text and Text-to-Speech for delivery worker interaction.
"""

import asyncio
import base64
import json
import os
import sys

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from google.adk.runners import Runner
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Add agents directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "agents"))
from orchestrator.agent import root_agent

APP_NAME = "gignav-voice"
app = FastAPI(title="GigNav Voice Interface")

session_service = InMemorySessionService()
runner = Runner(
    app_name=APP_NAME,
    agent=root_agent,
    session_service=session_service,
)


@app.get("/")
async def index():
    """Serve the voice interface."""
    html_path = os.path.join(os.path.dirname(__file__), "voice_ui.html")
    with open(html_path) as f:
        return HTMLResponse(f.read())


@app.get("/earnings")
async def earnings():
    """Serve the mock earnings page."""
    html_path = os.path.join(os.path.dirname(__file__), "mock_earnings.html")
    with open(html_path) as f:
        return HTMLResponse(f.read())


@app.get("/form")
async def form():
    """Serve the mock complaint form."""
    html_path = os.path.join(os.path.dirname(__file__), "mock_form.html")
    with open(html_path) as f:
        return HTMLResponse(f.read())


@app.websocket("/ws/{user_id}/{session_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, session_id: str):
    """WebSocket endpoint for real-time voice + text communication."""
    await websocket.accept()

    run_config = RunConfig(
        streaming_mode=StreamingMode.BIDI,
        response_modalities=["AUDIO"],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )

    session = await session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    if not session:
        await session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )

    live_request_queue = LiveRequestQueue()

    async def upstream():
        """Receive from browser, forward to agent."""
        try:
            while True:
                message = await websocket.receive()
                if "text" in message:
                    data = json.loads(message["text"])
                    if data.get("type") == "text":
                        content = types.Content(
                            parts=[types.Part(text=data["content"])]
                        )
                        live_request_queue.send_content(content)
                elif "bytes" in message:
                    audio_blob = types.Blob(
                        mime_type="audio/pcm;rate=16000",
                        data=message["bytes"],
                    )
                    live_request_queue.send_realtime(audio_blob)
        except WebSocketDisconnect:
            pass

    async def downstream():
        """Receive from agent, forward to browser."""
        try:
            async for event in runner.run_live(
                user_id=user_id,
                session_id=session_id,
                live_request_queue=live_request_queue,
                run_config=run_config,
            ):
                await websocket.send_text(
                    event.model_dump_json(exclude_none=True, by_alias=True)
                )
        except WebSocketDisconnect:
            pass

    try:
        await asyncio.gather(upstream(), downstream(), return_exceptions=True)
    finally:
        live_request_queue.close()


@app.websocket("/ws/text/{user_id}/{session_id}")
async def text_websocket(websocket: WebSocket, user_id: str, session_id: str):
    """Text-only WebSocket for fallback mode."""
    await websocket.accept()

    run_config = RunConfig(
        streaming_mode=StreamingMode.SSE,
        response_modalities=["TEXT"],
    )

    session = await session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    if not session:
        await session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            content = types.Content(
                role="user",
                parts=[types.Part(text=msg.get("content", ""))],
            )

            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=content,
                run_config=run_config,
            ):
                if hasattr(event, "content") and event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            await websocket.send_text(json.dumps({
                                "type": "text",
                                "content": part.text,
                            }))
    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
