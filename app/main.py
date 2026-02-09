"""
main.py (HTTP Server for Flutter/Dio)

- POST /start : receives child profile (JSON) and starts 120s free-chat window
- POST /chat  : handles chat + local curriculum routing + persona fallback
- GET/POST /health : health check
- GET / : simple OK

Reply format expected by Flutter:
"نص" (emotion) <motion>

Environment variables required:
- OPENAI_API_KEY_EMOTION
- OPENAI_API_KEY_MOTION
- OPENAI_API_KEY_PERSONA

Run (local):
    pip install -r requirements.txt
    python -m uvicorn main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
import sys
import threading
from typing import Any, Dict, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure local imports always resolve to this folder (avoid wrong duplicate modules)
APP_DIR = os.path.dirname(__file__)
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from Emotion import EmotionAgent  # noqa: E402
from transmission import MotionAgent  # noqa: E402
from Robot_paixi import PaixiRobot, PersonaInput  # noqa: E402


def _sanitize_quotes(s: str) -> str:
    """Make sure we don't break the reply wrapper quotes."""
    return (s or "").replace('"', "'").strip()


def _is_goodbye(text: str) -> bool:
    t = (text or "").strip().lower()
    goodbye_markers = [
        "وداعا",
        "وداعًا",
        "مع السلامة",
        "سلام",
        "خروج",
        "اخرج",
        "اطلع",
        "وداعا بيكسي",
        "وداعًا بيكسي",
        "وداعا بايكسي",
        "bye",
        "goodbye",
        "exit",
        "quit",
    ]
    return any(m in t for m in goodbye_markers)


def _shutdown_soon() -> None:
    def _exit() -> None:
        os._exit(0)

    threading.Timer(0.25, _exit).start()


def _call_try_local(paixi: PaixiRobot, persona_input: PersonaInput) -> Optional[str]:
    """
    Prevent server crash if try_local doesn't exist or has a different signature
    (supports some older versions).
    """
    fn = getattr(paixi, "try_local", None)
    if not callable(fn):
        return None

    try:
        return fn(persona_input)
    except TypeError:
        # Possible old signature: try_local(text, profile_dict, ...)
        try:
            return fn(persona_input.user_text, persona_input.child_profile_dict, None)
        except Exception:
            return None
    except Exception:
        return None


app = FastAPI(title="Paixi Agent API")

# CORS for LAN testing (phone -> PC / Cloud Run)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

# Debug prints (optional)
if os.getenv("PAIXI_DEBUG") == "1":
    import Robot_paixi as _rp  # noqa: E402

    print("Robot_paixi loaded from:", _rp.__file__)
    print("Has PaixiRobot.reply ?", hasattr(PaixiRobot, "reply"))
    print("Has PaixiRobot.try_local ?", hasattr(PaixiRobot, "try_local"))

# Agents
emotion_agent = EmotionAgent()
motion_agent = MotionAgent()
paixi = PaixiRobot(knowledge_root=".")

# State
session_start_ts: Optional[float] = None
session_id: Optional[str] = None
child_profile_text: str = ""
child_profile_dict: Dict[str, Any] = {}
current_motion: int = 0


class StartPayload(BaseModel):
    profile: Dict[str, Any]


class ChatPayload(BaseModel):
    text: str
    learning_materials: Optional[Any] = None
    learning_topics: Optional[Any] = None
    learning_hours: Optional[float] = None
    profile_update: Optional[Dict[str, Any]] = None


@app.get("/")
def root() -> Dict[str, str]:
    return {"status": "OK"}


@app.get("/health")
@app.post("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/start")
def start(payload: StartPayload) -> Dict[str, Any]:
    global child_profile_text, child_profile_dict, current_motion
    global session_start_ts, session_id

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

    # session timer (free chat window)
    import time as _time

    session_start_ts = _time.time()
    session_id = str(
        child_profile_dict.get("session_id") or child_profile_dict.get("sessionId") or ""
    ).strip() or None

    agent_text = f"اهلا {name}"
    return {"reply": f"\"{_sanitize_quotes(agent_text)}\" (normal) <0>"}


@app.post("/chat")
def chat(payload: ChatPayload) -> Dict[str, Any]:
    global current_motion, child_profile_text, child_profile_dict, session_start_ts

    user_text = (payload.text or "").strip()

    # Shutdown rule
    if _is_goodbye(user_text):
        _shutdown_soon()
        return {"reply": "Off"}

    # Child can pause curriculum and chat only by saying: اجله يا بيكسي
    if user_text.replace(" ", "") == "اجلهيابيكسي" or "اجله يا بيكسي" in user_text:
        prog = child_profile_dict.get("progress")
        prog = dict(prog) if isinstance(prog, dict) else {}
        prog["phase"] = "chat"
        prog["await_new_session"] = False
        prog["curriculum_paused"] = True
        child_profile_dict["progress"] = prog
        return {"reply": "\"حسنا خلي نسولف\" (Teacher) <0>", "progress_update": prog}

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

    # Enforce 120s free-chat timer after /start
    try:
        import time as _time

        if session_start_ts is not None and (_time.time() - float(session_start_ts)) < 120.0:
            prog = child_profile_dict.get("progress")
            prog = dict(prog) if isinstance(prog, dict) else {}
            prog["phase"] = "chat"
            prog["await_new_session"] = False
            child_profile_dict["progress"] = prog
    except Exception:
        pass

    # 1) Local/deterministic curriculum first (if available)
    local = _call_try_local(
        paixi,
        PersonaInput(
            user_text=user_text,
            emotion="normal",
            motion_int=current_motion,
            child_profile=child_profile_text,
            child_profile_dict=child_profile_dict,
            extra_event="",
            language_mode="auto",
        ),
    )
    if local:
        pu = getattr(paixi, "_last_progress_update", None)
        if isinstance(pu, dict):
            return {"reply": local, "progress_update": pu}
        return {"reply": local}

    # 2) Emotion + Motion inference
    emo = emotion_agent.analyze(user_text)
    motion_decision = motion_agent.decide(user_text, default_state=current_motion)
    current_motion = int(getattr(motion_decision, "primary", current_motion))

    extra_event = ""
    emotion_name = getattr(emo, "emotion", "normal") or "normal"
    if emotion_name == "happy":
        extra_event = "very_happy"
    elif emotion_name == "sad":
        extra_event = "sad"
    elif emotion_name == "frustration":
        extra_event = "wrong_answer"

    # 3) Persona reply (OpenAI)
    reply_text = paixi.reply(
        PersonaInput(
            user_text=user_text,
            emotion=emotion_name,
            motion_int=current_motion,
            child_profile=child_profile_text,
            child_profile_dict=child_profile_dict,
            extra_event=extra_event,
            language_mode="auto",
        )
    )

    stripped = (reply_text or "").strip()
    pu = getattr(paixi, "_last_progress_update", None)

    # If reply already formatted: "..." (emotion) <...>
    if stripped.startswith('"') and "(" in stripped and "<" in stripped:
        if isinstance(pu, dict):
            return {"reply": stripped, "progress_update": pu}
        return {"reply": stripped}

    # Otherwise wrap it
    wrapped = f"\"{_sanitize_quotes(reply_text)}\" ({emotion_name}) <{current_motion}>"
    if isinstance(pu, dict):
        return {"reply": wrapped, "progress_update": pu}
    return {"reply": wrapped}
