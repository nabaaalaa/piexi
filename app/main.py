"""
main.py (HTTP Server for Flutter/Dio)

Endpoints:
- POST /start  : receives child's profile (JSON) and replies greeting.
- POST /chat   : receives chat message (JSON) and replies as:
    "<agent text>" (Emotion) <MotionInt>
- GET/POST /health : health check
- GET /        : simple OK (optional, avoids {"detail":"Not Found"} on base URL)

Shutdown rule:
If user sends a goodbye intent (e.g., "وداعا بيكسي", "خروج", "bye", etc.)
the server replies with: Off
then exits the process.

Environment variables required:
- OPENAI_API_KEY_EMOTION
- OPENAI_API_KEY_MOTION
- OPENAI_API_KEY_PERSONA

Run (local):
    pip install -r requirements.txt
    uvicorn main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
import threading
from typing import Any, Dict, Optional

from fastapi import FastAPI
from pydantic import BaseModel

from Emotion import EmotionAgent
from transmission import MotionAgent
from Robot_paixi import PaixiRobot, PersonaInput


def _sanitize_quotes(s: str) -> str:
    # Prevent breaking the required " ... " wrapper
    return (s or "").replace('"', "'").strip()


def _is_goodbye(text: str) -> bool:
    t = (text or "").strip().lower()
    goodbye_markers = [
        "وداعا", "وداعًا", "مع السلامة", "سلام", "خروج", "اخرج", "اطلع",
        "وداعا بيكسي", "وداعًا بيكسي", "وداعا بايكسي",
        "bye", "goodbye", "exit", "quit"
    ]
    return any(m in t for m in goodbye_markers)


def _shutdown_soon() -> None:
    def _exit() -> None:
        os._exit(0)

    threading.Timer(0.25, _exit).start()


app = FastAPI(title="Paixi Agent API")

# Agents
emotion_agent = EmotionAgent()
motion_agent = MotionAgent()
paixi = PaixiRobot(knowledge_root=".")

# State
child_profile_text: str = ""
child_profile_dict: Dict[str, Any] = {}
current_motion: int = 0


class StartPayload(BaseModel):
    profile: Dict[str, Any]


class ChatPayload(BaseModel):
    text: str
    # Optional learning-plan updates sent by the app (backward compatible)
    learning_materials: Optional[Any] = None
    learning_topics: Optional[Any] = None
    learning_hours: float | None = None
    profile_update: Optional[Dict[str, Any]] = None


@app.get("/")
def root() -> Dict[str, str]:
    return {"status": "OK"}


@app.get("/health")
@app.post("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/start")
def start(payload: StartPayload) -> Dict[str, str]:
    global child_profile_text, child_profile_dict, current_motion

    child_profile_dict = dict(payload.profile)
    child_profile_text = str(child_profile_dict)

    name = (
        payload.profile.get("name")
        or payload.profile.get("kidName")
        or payload.profile.get("fullname")
        or ""
    )
    name = str(name).strip() or "صديقي"

    current_motion = 0
    agent_text = f"اهلا ب @{name}"

    return {"reply": f"\"{_sanitize_quotes(agent_text)}\" (normal) <0>"}


@app.post("/chat")
def chat(payload: ChatPayload) -> Dict[str, str]:
    global current_motion, child_profile_text, child_profile_dict

    user_text = (payload.text or "").strip()

    # Shutdown rule
    if _is_goodbye(user_text):
        _shutdown_soon()
        return {"reply": "Off"}

    # Merge profile update
    if payload.profile_update:
        try:
            child_profile_dict.update(dict(payload.profile_update))
        except Exception:
            pass

    # Store learning-plan fields (if provided)
    if payload.learning_materials is not None:
        child_profile_dict["learning_materials"] = payload.learning_materials
    if payload.learning_topics is not None:
        child_profile_dict["learning_topics"] = payload.learning_topics
    if payload.learning_hours is not None:
        child_profile_dict["learning_hours"] = payload.learning_hours

    child_profile_text = str(child_profile_dict)

    # 1) Local/deterministic handlers first
    local = paixi.try_local(
        PersonaInput(
            user_text=user_text,
            emotion="normal",
            motion_int=current_motion,
            child_profile=child_profile_text,
            child_profile_dict=child_profile_dict,
            extra_event="",
            language_mode="auto",
        )
    )
    if local:
        stripped_local = (local or "").strip()
        # If already formatted, return as-is
        if stripped_local.startswith('"') and "(" in stripped_local and "<" in stripped_local:
            return {"reply": stripped_local}
        # Otherwise wrap it
        return {"reply": f"\"{_sanitize_quotes(stripped_local)}\" (normal) <{int(current_motion)}>"}

    # 2) Emotion + Motion inference
    emo = emotion_agent.analyze(user_text)

    motion_decision = motion_agent.decide(user_text, default_state=current_motion)
    current_motion = int(getattr(motion_decision, "primary", current_motion))

    extra_event = ""
    if getattr(emo, "emotion", "") == "happy":
        extra_event = "very_happy"
    elif getattr(emo, "emotion", "") == "sad":
        extra_event = "sad"
    elif getattr(emo, "emotion", "") == "frustration":
        extra_event = "wrong_answer"

    # 3) Main reply
    reply_text = paixi.reply(
        PersonaInput(
            user_text=user_text,
            emotion=getattr(emo, "emotion", "normal"),
            motion_int=current_motion,
            child_profile=child_profile_text,
            child_profile_dict=child_profile_dict,
            extra_event=extra_event,
            language_mode="auto",
        )
    )

    # If reply_text is already formatted like: "..." (emotion) <...>
    stripped = (reply_text or "").strip()
    if stripped.startswith('"') and "(" in stripped and "<" in stripped:
        return {"reply": stripped}

    # Otherwise, enforce the required format
    emotion_name = getattr(emo, "emotion", "normal") or "normal"
    return {"reply": f"\"{_sanitize_quotes(stripped)}\" ({emotion_name}) <{int(current_motion)}>"}
