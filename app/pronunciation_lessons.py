"""pronunciation_lessons.py
Subject: تعلم النطق (الفصل الاول: حرف الالف)

Rules per lesson:
- Ask child to repeat the target sound.
- If wrong: emotion frustration, ask try again.
- If correct: emotion celebrate, praise and ask repeat again.
- Two correct attempts => complete lesson.
- Ten wrong attempts => skip to next lesson.

State used (lesson_state):
  - started: bool
  - correct: int
  - wrong: int
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from lesson_base import clean_arabic_plain, norm_arabic

_LESSONS = {
    1: {"target": "ااا", "prompt": "لفظ حرف الالف هكذا ااا وقلها بعدي"},
    2: {"target": "ءء", "prompt": "لفظ الهمزة هكذا ءء وقلها بعدي"},
    3: {"target": "اااأ", "prompt": "لفظ الالف هكذا اااأ وقلها بعدي"},
    4: {"target": "ى", "prompt": "لفظ الالف المقصورة هكذا ى وقلها بعدي"},
    5: {"target": "ىِ", "prompt": "لفظ الالف المقصورة مع الكسرة هكذا ىِ وقلها بعدي"},
}

def start_lesson(profile: Dict[str, Any], lesson_no: int) -> Tuple[str, Dict[str, Any], str]:
    info = _LESSONS.get(int(lesson_no)) or _LESSONS[1]
    text = clean_arabic_plain(info["prompt"])
    state = {"correct": 0, "wrong": 0}
    return text, state, "Teacher"

def handle_turn(profile: Dict[str, Any], lesson_no: int, user_text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool, str]:
    info = _LESSONS.get(int(lesson_no)) or _LESSONS[1]
    target = info["target"]
    state = dict(state or {})
    state["correct"] = int(state.get("correct") or 0)
    state["wrong"] = int(state.get("wrong") or 0)

    ok = norm_arabic(user_text) == norm_arabic(target)

    if ok:
        state["correct"] += 1
        if state["correct"] >= 2:
            return clean_arabic_plain("احسنت خلصنا الدرس"), state, True, "celebrate"
        else:
            return clean_arabic_plain("احسنت كررها مرة ثانية"), state, False, "celebrate"

    state["wrong"] += 1
    if state["wrong"] >= 10:
        return clean_arabic_plain("حسنا ننتقل للدرس التالي"), state, True, "frustration"

    return clean_arabic_plain("مو مثلها حاول مرة ثانية"), state, False, "frustration"
