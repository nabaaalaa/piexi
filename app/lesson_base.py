"""lesson_base.py
Stateless lesson helpers.
- Lessons are driven by a curriculum provided by Flutter (in profile dict).
- Progress is stored in Flutter; the server only returns suggested progress updates.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Tuple

_AR_ONLY_RE = re.compile(r"[^\u0600-\u06FF\s]")

def clean_arabic_plain(text: str, max_len: int = 120) -> str:
    """Keep only Arabic letters + spaces. Collapse whitespace."""
    t = (text or "").strip()
    t = _AR_ONLY_RE.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > max_len:
        t = t[:max_len].rsplit(" ", 1)[0].strip() or t[:max_len]
    return t

def get_curriculum(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Curriculum container expected from Flutter."""
    cur = profile.get("curriculum")
    return cur if isinstance(cur, dict) else {}

def get_lessons(cur: Dict[str, Any], subject: str) -> list:
    subj = cur.get(subject)
    return subj if isinstance(subj, list) else []

def get_lesson(cur: Dict[str, Any], subject: str, lesson_no: int) -> Dict[str, Any]:
    lessons = get_lessons(cur, subject)
    idx = max(0, int(lesson_no) - 1)
    if 0 <= idx < len(lessons) and isinstance(lessons[idx], dict):
        return lessons[idx]
    return {}

_DIACRITICS_RE = re.compile(r"[\u064B-\u0652]")  # tashkeel

def norm_arabic(text: str) -> str:
    """Normalize Arabic text for simple matching: keep Arabic letters, remove spaces/diacritics, unify alef forms."""
    t = clean_arabic_plain(text, max_len=500)
    t = _DIACRITICS_RE.sub("", t)
    # unify alef variants
    t = t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    t = t.replace("ؤ", "و").replace("ئ", "ي")
    t = t.replace("ة", "ه")
    t = t.replace("ى", "ي")
    t = re.sub(r"\s+", "", t)
    return t.strip()
