"""
Robot_paixi.py
"""
from __future__ import annotations

import os
import re
import pathlib
import textwrap
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple

from openai import OpenAI

import pronunciation_lessons
import reading_lessons
import stories_lessons
import world_lessons

from lesson_base import clean_arabic_plain

# ----------------------------
# Helpers
# ----------------------------

def _clean_inside_quotes(text: str) -> str:
    """Keep only Arabic letters + spaces inside the quoted text."""
    return clean_arabic_plain(text, max_len=120)

def _format_reply(text: str, emotion: str, motions: List[int] | None = None) -> str:
    clean = _clean_inside_quotes(text)
    motion_part = "".join(f"<{int(m)}>" for m in (motions or [0])) or "<0>"
    return f"\"{clean}\" ({emotion}) {motion_part}"

# ----------------------------
# Curriculum Definitions
# ----------------------------
SUBJECT_ORDER = ["pronunciation", "reading", "stories", "world"]

_SUBJECT_STARTERS = {
    "pronunciation": pronunciation_lessons.start_lesson,
    "reading": reading_lessons.start_lesson,
    "stories": stories_lessons.start_lesson,
    "world": world_lessons.start_lesson,
}
_SUBJECT_HANDLERS = {
    "pronunciation": pronunciation_lessons.handle_turn,
    "reading": reading_lessons.handle_turn,
    "stories": stories_lessons.handle_turn,
    "world": world_lessons.handle_turn,
}

_LEARN_TIME_TRIGGERS = (
    "حان وقت تعلم", "حان وقت التعلّم", "وقت تعلم", "وقت التعلم",
    "حصة علوم", "حصة العلوم", "درس علوم", "درس العلوم",
    "خلينا نتعلم", "نبدأ نتعلم", "نبلش نتعلم",
    "اريد اتعلم", "أريد أتعلم", "اريد تعلم", "أريد تعلم",
    "نريد نتعلم", "علمني", "علمني علوم",
    "ابدي درس", "ابدأ درس", "يلا نتعلم", "خل نتعلم",
)

def _looks_like_learning_time(text: str) -> bool:
    t = (text or "").strip()
    return any(k in t for k in _LEARN_TIME_TRIGGERS)

def _get_progress(d: dict) -> dict:
    p = d.get("progress")
    return p if isinstance(p, dict) else {}

def _progress_subject_lesson(progress: dict) -> Tuple[str, int]:
    subj = progress.get("subject") or progress.get("current_subject") or SUBJECT_ORDER[0]
    if subj not in SUBJECT_ORDER:
        subj = SUBJECT_ORDER[0]
    lesson_no = progress.get("lesson") or progress.get("current_lesson") or 1
    try:
        lesson_no = int(lesson_no)
    except Exception:
        lesson_no = 1
    return subj, max(1, lesson_no)

def _advance_subject_lesson(subj: str, lesson_no: int) -> Tuple[str, int]:
    i = SUBJECT_ORDER.index(subj) if subj in SUBJECT_ORDER else 0
    if i < len(SUBJECT_ORDER) - 1:
        return SUBJECT_ORDER[i + 1], 1
    return SUBJECT_ORDER[0], lesson_no + 1

# ----------------------------
# Inputs & Knowledge
# ----------------------------

@dataclass
class PersonaInput:
    user_text: str
    emotion: str
    motion_int: int
    child_profile: str = ""
    child_profile_dict: dict | None = None
    extra_event: str = ""
    language_mode: str = "auto"

class LocalKnowledgeBase:
    def __init__(self, root: str = ".") -> None:
        self.root = pathlib.Path(root)
        self.folders = ["arabic_agent", "learn_animal", "learn_plants", "learn_reeding"]

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
# Main robot
# ----------------------------

class PaixiRobot:
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key_env: str = "OPENAI_API_KEY_PERSONA",
        knowledge_root: str = ".",
    ) -> None:
        api_key = os.getenv(api_key_env)
        # Fallback safety
        if not api_key:
             api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise RuntimeError(
                f"Missing {api_key_env}. Set it as an environment variable."
            )

        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.kb = LocalKnowledgeBase(root=knowledge_root)

        # Profile state placeholders
        self.learning_materials: list[str] = []
        self.learning_topics: list[str] = []
        self.learning_hours: float | None = None
        
        # This will store the side-effect of try_local for main.py to pick up
        self._last_progress_update: Dict[str, Any] | None = None

    def _extract_kid_name(self, profile_text: str) -> str:
        kid_name = "صديقي"
        prof = (profile_text or "")
        for key in ("name", "kidName", "fullname", "child", "kid"):
            m = re.search(rf"[\"']{key}[\"']\s*:\s*[\"']([^\"']+)[\"']", prof)
            if m:
                kid_name = (m.group(1).strip() or kid_name)
                break
        return kid_name

    def _force_stop_lessons(self) -> None:
        # Simplified: Just clear any internal state if needed
        # Previous code referenced self.arabic_lesson which didn't exist
        pass

    def try_local(self, p: PersonaInput) -> str | None:
        """
        Stateless curriculum routing.
        Returns ONLY the formatted reply string.
        """
        self._last_progress_update = None  # Reset per turn
        
        user_text = (p.user_text or "").strip()
        if not user_text:
            return None

        prof = p.child_profile_dict or {}
        progress = _get_progress(prof)
        kid_name = self._extract_kid_name(p.child_profile)

        if progress.get("await_new_session") is True:
            return None

        subject, lesson_no = _progress_subject_lesson(progress)
        lesson_state = progress.get("lesson_state")
        lesson_state = dict(lesson_state) if isinstance(lesson_state, dict) else {}

        wants_lesson = bool(progress.get("phase") == "lesson") or _looks_like_learning_time(user_text)
        if not wants_lesson:
            return None

        # 1. Start a new lesson?
        if lesson_state.get("started") is not True:
            starter = _SUBJECT_STARTERS.get(subject)
            if not starter:
                return None
            txt, st, emo = starter(prof, lesson_no)
            st = dict(st or {})
            st["started"] = True
            self._last_progress_update = {
                "current_subject": subject,
                "current_lesson": lesson_no,
                "lesson_state": st,
                "phase": "lesson",
            }
            return _format_reply(txt, emo or "Teacher", [0])

        # 2. Handle ongoing lesson turn
        handler = _SUBJECT_HANDLERS.get(subject)
        if not handler:
            return None
        txt, st, done, emo = handler(prof, lesson_no, user_text, lesson_state)
        st = dict(st or {})
        st["started"] = True

        if done:
            next_subject, next_lesson = _advance_subject_lesson(subject, lesson_no)
            self._last_progress_update = {
                "current_subject": next_subject,
                "current_lesson": next_lesson,
                "lesson_state": {},
                "phase": "chat",
                "await_new_session": True,
            }
            outro = clean_arabic_plain(f"احسنت {kid_name} خلصنا الدرس هسه سوالف وبعدين نكمل")
            return _format_reply(outro, "Teacher", [0])

        self._last_progress_update = {
            "current_subject": subject,
            "current_lesson": lesson_no,
            "lesson_state": st,
            "phase": "lesson",
        }
        return _format_reply(txt, emo or "Teacher", [0])

    def reply(self, p: PersonaInput) -> str:
        """OpenAI personality response."""
        user_text = (p.user_text or "").strip()
        kb_context = self.kb.build_context()

        context_block = ""
        if kb_context:
            context_block = (
                "Local learning notes (may be used when helpful):\n"
                + kb_context[:1200]
            )

        style = (
            "Write in Arabic. Keep sentences short (for age 5-12). "
            "Avoid long paragraphs. Avoid emojis unless the child used them first."
        )
        if p.language_mode == "fusha":
            style = "Write in Modern Standard Arabic only. Keep it short and simple."
        elif p.language_mode == "iraqi":
            style = "Write in Iraqi Arabic (لهجة عراقية) but still clear. Keep it short."

        system_instructions = textwrap.dedent(
            f"""
            You are "Paixi" — a friendly robot for kids (5-12).
            Personality: kind, optimistic, responsible, smart when teaching. Simple & short sentences.

            Child profile: {p.child_profile}

            Current Context:
            - Emotion label: {p.emotion}
            - Motion command (int): {p.motion_int}
            - Optional event: {p.extra_event}

            Behavior rules:
            - If emotion is "sad": comfort + encourage gently.
            - If emotion is "fraid": reassure safety.
            - If emotion is "Teacher": answer as a tiny lesson + ask a small question.
            - If emotion is "celebrate": praise.
            - If emotion is "frustration": calm them and give a small hint.
            - Otherwise: friendly chat + one question.

            {style}

            {context_block}
            """
        ).strip()

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_instructions},
                    {"role": "user", "content": user_text}
                ]
            )
            out = resp.choices[0].message.content or ""
        except Exception as e:
            print(f"Persona API Error: {e}")
            out = "اهلا يا صديقي"

        # Return clean text only (main.py will wrap with emotion/motion)
        return _clean_inside_quotes(out) or "شنو تحب نسوي هسه"