"""
Robot_paixi.py
- Uses a dedicated OpenAI API key (env var: OPENAI_API_KEY_PERSONA)
- Generates the assistant's text response (the robot's personality).
- Also routes to local deterministic lesson modules when the child starts a lesson.

Local lesson modules:
- arabic_agent.py        (Arabic spelling lesson)
- learn_animal.py        (Science warm-up: animals)
- learn_plants.py        (Science warm-up: plants)

NOTE:
- The text *inside* quotes must be clean/plain (no symbols like: * ^ & , ) | \, ؟ ...).
"""

from __future__ import annotations

import os
import re
import pathlib
import textwrap
import time
from dataclasses import dataclass
from typing import List, Optional

from openai import OpenAI

from arabic_agent import ArabicLessonAgent
from learn_animal import AnimalLessonAgent
from learn_plants import PlantLessonAgent


# ----------------------------
# Helpers
# ----------------------------

def _clean_inside_quotes(text: str) -> str:
    """Keep only letters/digits/spaces (Arabic + English). Remove punctuation/symbols."""
    t = (text or "").strip()
    kept = []
    for ch in t:
        if ch.isalnum() or ch.isspace():
            kept.append(ch)
        else:
            # drop punctuation/symbols مثل ؟ , * ^ & ) | \
            kept.append(" ")
    out = "".join(kept)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def _format_reply(text: str, emotion: str, motions: List[int] | None = None) -> str:
    clean = _clean_inside_quotes(text)
    motion_part = "".join(f"<{int(m)}>" for m in (motions or [0])) or "<0>"
    return f"\"{clean}\" ({emotion}) {motion_part}"


# ----------------------------
# Inputs
# ----------------------------

@dataclass
class PersonaInput:
    user_text: str
    emotion: str
    motion_int: int
    child_profile: str = ""  # raw profile info from Flutter
    child_profile_dict: dict | None = None  # structured profile from Flutter (optional)
    extra_event: str = ""  # e.g. "wrong_answer", "very_happy"
    language_mode: str = "auto"  # "auto" | "fusha" | "iraqi"


class LocalKnowledgeBase:
    """
    Minimal local context loader (no extra dependencies).
    Reads short text from .txt/.md files in the provided folders, if they exist.
    """

    def __init__(self, root: str = ".") -> None:
        self.root = pathlib.Path(root)
        self.folders = [
            "arabic_agent",
            "learn_animal",
            "learn_plants",
            "learn_reeding",
        ]

    def _read_folder_snippets(self, folder: str, max_chars: int = 900) -> str:
        p = (self.root / folder)
        if not p.exists() or not p.is_dir():
            return ""

        parts: List[str] = []
        for ext in (".txt", ".md"):
            for f in sorted(p.rglob(f"*{ext}")):
                try:
                    txt = f.read_text(encoding="utf-8", errors="ignore").strip()
                except Exception:
                    continue
                if not txt:
                    continue
                parts.append(f"[{folder}/{f.name}]\n{txt[:400]}")
                if sum(len(x) for x in parts) >= max_chars:
                    break
            if sum(len(x) for x in parts) >= max_chars:
                break

        out = "\n\n".join(parts).strip()
        return out[:max_chars]

    def build_context(self) -> str:
        snippets = []
        for folder in self.folders:
            s = self._read_folder_snippets(folder)
            if s:
                snippets.append(s)
        return "\n\n".join(snippets).strip()


# ----------------------------
# Local routing utilities
# ----------------------------

_LEARN_TIME_TRIGGERS = (
    "حان وقت تعلم",
    "حان وقت التعلّم",
    "وقت تعلم",
    "وقت التعلم",
    "حصة علوم",
    "حصة العلوم",
    "درس علوم",
    "درس العلوم",
    "خلينا نتعلم",
    "نبدأ نتعلم",
    "نبلش نتعلم",
    "اريد اتعلم",
    "أريد أتعلم",
    "اريد تعلم",
    "أريد تعلم",
    "نريد نتعلم",
    "علمني",
    "علمني علوم",
    "ابدي درس",
    "ابدأ درس",
    "يلا نتعلم",
    "خل نتعلم",
)


def _looks_like_learning_time(text: str) -> bool:
    t = (text or "").strip()
    return any(k in t for k in _LEARN_TIME_TRIGGERS)


def _sanitize_formatted(formatted: str) -> str:
    """
    Ensure the quoted part is clean/plain, keep the wrapper: "..." (Emotion) <...>
    """
    s = (formatted or "").strip()
    # Extract quoted text if exists
    m = re.search(r'"(.*?)"', s)
    if not m:
        # no quotes -> treat as plain
        return _format_reply(s, "Teacher", [0])

    inner = m.group(1)
    clean_inner = _clean_inside_quotes(inner)

    # Replace first quoted segment
    s2 = s[:m.start()] + f'"{clean_inner}"' + s[m.end():]
    return s2.strip()


# ----------------------------
# Main robot
# ----------------------------

class PaixiRobot:
    """
    Personality agent: kind, optimistic, responsible, and smart when teaching.
    Also includes small local lesson agents for learning mode.
    """

    def __init__(
        self,
        model: str = "gpt-5.2",
        api_key_env: str = "OPENAI_API_KEY_PERSONA",
        knowledge_root: str = ".",
    ) -> None:
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise RuntimeError(
                f"Missing {api_key_env}. Set it as an environment variable for Robot_paixi.py."
            )

        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.kb = LocalKnowledgeBase(root=knowledge_root)

        # Local lesson agents (deterministic/stateful)
        self.arabic_lesson = ArabicLessonAgent()
        self.animal_lesson = AnimalLessonAgent()
        self.plant_lesson = PlantLessonAgent()

        # Learning plan (can be provided by the app in the profile)
        self.learning_materials: list[str] = []
        self.learning_topics: list[str] = []
        self.learning_hours: float | None = None
        self.lesson_end_ts: float | None = None

    def _extract_kid_name(self, profile_text: str) -> str:
        kid_name = "صديقي"
        prof = (profile_text or "")

        # tries to match both 'name': 'X' and "name": "X"
        for key in ("name", "kidName", "fullname", "child", "kid"):
            m = re.search(rf"[\"']{key}[\"']\s*:\s*[\"']([^\"']+)[\"']", prof)
            if m:
                kid_name = (m.group(1).strip() or kid_name)
                break
        return kid_name

    def _force_stop_lessons(self) -> None:
        # End any running local lesson sessions
        try:
            # ArabicLessonAgent uses state.active in your codebase
            self.arabic_lesson.state.active = False
        except Exception:
            pass
        try:
            # AnimalLessonAgent may use active
            self.animal_lesson.active = False
        except Exception:
            pass
        try:
            # PlantLessonAgent may use active
            self.plant_lesson.active = False
        except Exception:
            pass

    def _update_learning_plan_from_profile(self, profile_dict: dict | None) -> None:
        """Read lesson plan from structured profile dict (if provided by the app)."""
        if not profile_dict:
            return

        materials = (
            profile_dict.get("learning_materials")
            or profile_dict.get("materials")
            or profile_dict.get("subjects")
            or profile_dict.get("learning_subjects")
        )
        if isinstance(materials, str):
            materials = [x.strip() for x in materials.split(",") if x.strip()]
        if isinstance(materials, list):
            self.learning_materials = [str(x).strip() for x in materials if str(x).strip()]

        topics = profile_dict.get("learning_topics") or profile_dict.get("topics")
        if isinstance(topics, str):
            topics = [x.strip() for x in topics.split(",") if x.strip()]
        if isinstance(topics, list):
            self.learning_topics = [str(x).strip() for x in topics if str(x).strip()]

        hours = profile_dict.get("learning_hours") or profile_dict.get("hours") or profile_dict.get("lesson_hours")
        if isinstance(hours, (int, float)) and hours > 0:
            self.learning_hours = float(hours)

    def _materials_hint(self) -> str:
        """Return a short Arabic list of available materials for the child."""
        mats = [m for m in (self.learning_materials or [])]
        mapped = []
        for m in mats:
            k = m.strip().lower()
            if k in ("animals", "animal", "learn_animal", "حيوانات"):
                mapped.append("حيوانات")
            elif k in ("plants", "plant", "learn_plants", "نباتات"):
                mapped.append("نباتات")
            elif k in ("arabic", "arabic_agent", "عربي", "لغة عربية"):
                mapped.append("عربي")
            else:
                mapped.append(m)

        seen = set()
        uniq = []
        for x in mapped:
            if x not in seen:
                seen.add(x)
                uniq.append(x)

        return " او ".join(uniq) if uniq else "حيوانات لو نباتات لو عربي"

    def try_local(self, p: PersonaInput) -> str | None:
        """
        Local learning routing:
        - If any lesson is active, continue it.
        - Otherwise, start a lesson when user says it's time to learn.
        - The app may provide a learning plan (materials + hours) in the profile dict.
        Returns formatted string: "<text>" (Emotion) <motion>
        """
        user_text = (p.user_text or "").strip()
        if not user_text:
            return None

        kid_name = self._extract_kid_name(p.child_profile)

        # Update learning plan from structured profile (if provided)
        self._update_learning_plan_from_profile(p.child_profile_dict)

        # Enforce time limit if the app provided lesson hours and a lesson is running
        if self.lesson_end_ts is not None and time.time() >= self.lesson_end_ts:
            self._force_stop_lessons()
            self.lesson_end_ts = None
            txt = f"خلص وقت الدرس هسه {kid_name} خلينا نلخص بسرعة وتكدر نكمل بعدين"
            return _format_reply(txt, "Teacher", [0])

        # If a lesson is active and we have hours but end_ts not set yet, set it
        if self.lesson_end_ts is None and self.learning_hours:
            try:
                active_any = (
                    self.arabic_lesson.in_session()
                    or self.animal_lesson.in_session()
                    or self.plant_lesson.in_session()
                )
            except Exception:
                # If some agents don't have in_session, ignore
                active_any = False
            if active_any:
                self.lesson_end_ts = time.time() + (self.learning_hours * 3600.0)

        # 1) continue active lessons (priority order)
        try:
            if self.arabic_lesson.in_session():
                out = self.arabic_lesson.handle(user_text)
                if out:
                    return _sanitize_formatted(out)
        except Exception:
            pass

        try:
            if self.animal_lesson.in_session():
                out = self.animal_lesson.handle(user_text, kid_name=kid_name)
                if out:
                    return _sanitize_formatted(out)
        except Exception:
            pass

        try:
            if self.plant_lesson.in_session():
                out = self.plant_lesson.handle(user_text, kid_name=kid_name)
                if out:
                    return _sanitize_formatted(out)
        except Exception:
            pass

        # 2) start Arabic lesson if triggered
        starter = None
        try:
            starter = self.arabic_lesson.maybe_start(user_text, kid_name=kid_name)
        except Exception:
            starter = None
        if starter:
            if self.learning_hours and self.lesson_end_ts is None:
                self.lesson_end_ts = time.time() + (self.learning_hours * 3600.0)
            return _sanitize_formatted(starter)

        # 3) start science lessons
        starter = None
        try:
            starter = self.animal_lesson.maybe_start(user_text, kid_name=kid_name)
        except Exception:
            starter = None
        if starter:
            if self.learning_hours and self.lesson_end_ts is None:
                self.lesson_end_ts = time.time() + (self.learning_hours * 3600.0)
            return _sanitize_formatted(starter)

        starter = None
        try:
            starter = self.plant_lesson.maybe_start(user_text, kid_name=kid_name)
        except Exception:
            starter = None
        if starter:
            if self.learning_hours and self.lesson_end_ts is None:
                self.lesson_end_ts = time.time() + (self.learning_hours * 3600.0)
            return _sanitize_formatted(starter)

        # 4) generic "learning time" -> ask which one
        if _looks_like_learning_time(user_text):
            txt = f"تمام {kid_name} شنو تحب نتعلم هسه {self._materials_hint()}"
            return _format_reply(txt, "Teacher", [0])

        return None

    def reply(self, p: PersonaInput) -> str:
        """OpenAI personality response (fallback when no local lesson applies)."""
        user_text = (p.user_text or "").strip()
        kb_context = self.kb.build_context()

        context_block = ""
        if kb_context:
            context_block = (
                "Local learning notes (may be used when helpful):\n"
                + kb_context[:1200]
            )

        # Style
        style = (
            "Write in Arabic. Keep sentences short (for age 5-12). "
            "Avoid long paragraphs. Avoid emojis unless the child used them first."
        )
        if p.language_mode == "fusha":
            style = "Write in Modern Standard Arabic only. Keep it short and simple for age 5-12."
        elif p.language_mode == "iraqi":
            style = "Write in Iraqi Arabic (لهجة عراقية) but still clear and child-friendly. Keep it short."

        instructions = textwrap.dedent(
            f"""
            You are "Paixi" — a friendly robot for kids (5-12).
            Personality: kind, optimistic, responsible, smart when teaching. Simple & short sentences.

            Safety:
            - Avoid scary/unsafe instructions. If the child asks for something dangerous, refuse gently and suggest safe alternatives.

            Child profile:
            - Use this only to adapt tone and teaching style (age, interests, etc.).
            - Do NOT repeat private details back verbatim; keep it general.
            - Profile text: {p.child_profile}

            You are given:
            - Emotion label: {p.emotion}
            - Motion command (int): {p.motion_int}
            - Optional event: {p.extra_event}

            Behavior rules:
            - If emotion is "sad": comfort + encourage gently.
            - If emotion is "fraid": reassure safety; suggest telling a trusted adult; keep it calm.
            - If emotion is "Teacher": answer as a tiny lesson + ask a small question.
            - If emotion is "celebrate": praise and keep it positive.
            - If emotion is "frustration": calm them and give a small hint.
            - Otherwise: friendly chat + one question to continue.

            {style}

            {context_block}
            """
        ).strip()

        resp = self.client.responses.create(
            model=self.model,
            instructions=instructions,
            input=user_text,
        )
        out = getattr(resp, "output_text", "") or ""
        # Return clean text only (main.py will wrap with emotion/motion)
        return _clean_inside_quotes(out) or "شنو تحب نسوي هسه"
