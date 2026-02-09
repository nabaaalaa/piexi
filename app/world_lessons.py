"""world_lessons.py
Subject: معلومات حول العالم (الفصل الاول: نبات)

For each lesson:
- Give a short simple fact.
- Ask child to tell you one simple thing about the topic.
- Two correct attempts => complete lesson.
- Ten wrong attempts => skip lesson.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from lesson_base import clean_arabic_plain, norm_arabic

_LESSONS = {
    1: {"topic": "الجذر", "fact": "الجذر جزء تحت الارض يمسك النبات ويمتص الماء", "keywords": ["جذر", "يمتص", "ماء", "تحت", "ارض"]},
    2: {"topic": "الساق", "fact": "الساق يحمل الاوراق والزهور وينقل الماء داخل النبات", "keywords": ["ساق", "يحمل", "ينقل", "ماء", "نبات"]},
    3: {"topic": "الورق", "fact": "الورق يصنع غذاء النبات بمساعدة ضوء الشمس", "keywords": ["ورق", "غذاء", "شمس", "ضوء", "يصنع"]},
    4: {"topic": "الزهرة", "fact": "الزهرة تساعد النبات على تكوين الثمرة والبذور", "keywords": ["زهرة", "ثمرة", "بذور", "تكوين", "نبات"]},
    5: {"topic": "الثمرة", "fact": "الثمرة تحمي البذور ونأكل بعض الثمار مثل التفاح", "keywords": ["ثمرة", "بذور", "نأكل", "تفاح", "تحمي"]},
}


def start_lesson(profile: Dict[str, Any], lesson_no: int) -> Tuple[str, Dict[str, Any], str]:
    info = _LESSONS.get(int(lesson_no)) or _LESSONS[1]
    text = clean_arabic_plain(f"{info['fact']} قل لي شي عن {info['topic']}")
    state = {"correct": 0, "wrong": 0}
    return text, state, "Teacher"

def handle_turn(profile: Dict[str, Any], lesson_no: int, user_text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool, str]:
    info = _LESSONS.get(int(lesson_no)) or _LESSONS[1]
    state = dict(state or {})
    state["correct"] = int(state.get("correct") or 0)
    state["wrong"] = int(state.get("wrong") or 0)

    ut = norm_arabic(user_text)
    ok = any(norm_arabic(k) in ut for k in info["keywords"])

    if ok:
        state["correct"] += 1
        if state["correct"] >= 2:
            return clean_arabic_plain("احسنت خلصنا الدرس"), state, True, "celebrate"
        else:
            return clean_arabic_plain("احسنت قلها مرة ثانية"), state, False, "celebrate"

    state["wrong"] += 1
    if state["wrong"] >= 10:
        return clean_arabic_plain("حسنا ننتقل للدرس التالي"), state, True, "frustration"

    return clean_arabic_plain("مو هذا قصدي حاول مرة ثانية"), state, False, "frustration"
