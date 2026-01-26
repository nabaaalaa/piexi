"""
learn_animal.py
Deterministic science warm-up lesson (animals) for children.

Goal:
- Fun, short, teacher-style Q&A.
- Keyword-based checking (no external dependencies).
- Returns formatted strings: "<text>" (Teacher) <0>

This module is designed to be called from Robot_paixi.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict
import re


def _norm(text: str) -> str:
    t = (text or "").strip().lower()
    # Arabic normalize (light)
    t = re.sub(r"[\u064B-\u065F]", "", t)  # remove tashkeel
    t = t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    t = t.replace("ة", "ه")
    t = t.replace("ى", "ي")
    return t


def _fmt(text: str, emotion: str = "Teacher", motion: int = 0) -> str:
    # Keep it simple; Robot_paixi will sanitize the inside-quotes again.
    return f"\"{text.strip()}\" ({emotion}) <{int(motion)}>"


@dataclass
class _Topic:
    q: str
    correct_any: List[str]
    partial_any: List[str]
    hint_q: str
    explain: str


TOPICS: List[_Topic] = [
    _Topic(
        q="هل تعلم لماذا السمك لا يعيش على اليابسه",
        correct_any=["خياشيم", "لا يمتلك رئ", "يتنفس بالماء", "تنفس بالماء"],
        partial_any=["اقدام", "يمشي", "قدم"],
        hint_q="شنو الشي يساعدك تتنفس",
        explain="السمك يتنفس بالخياشيم مو بالرئتين لذلك خارج الماء يصير تنفسه صعب",
    ),
    _Topic(
        q="هل تعلم شنو يخزن الجمل داخل السنام مالته",
        correct_any=["دهون", "طاقه", "يخزن دهون"],
        partial_any=["ماء", "يشرب"],
        hint_q="لما نريد طاقه من الاكل شنو نسميها داخل الجسم",
        explain="السنام يخزن دهون مو ماء والدهون تتحول لطاقة وتساعده يتحمل الصحرا",
    ),
    _Topic(
        q="ليش البطريق ما يطير مثل باقي الطيور",
        correct_any=["يسبح", "جسمه ثقيل", "جناح للسباحه"],
        partial_any=["جناح صغير", "كسلان"],
        hint_q="وين يعيش البطريق اكثر شي بالمي لو بالهواء",
        explain="البطريق اجنحته صارت مثل زعانف تساعده يسبح وجسمه ثقيل فمو مهيأ للطيران",
    ),
]


class AnimalLessonAgent:
    START_TRIGGERS = (
        "تعلم الحيوانات",
        "درس الحيوانات",
        "حصة الحيوانات",
        "حصة العلوم",
        "درس العلوم",
        "نبدأ حيوانات",
        "نبلش حيوانات",
        "حيوانات",
        "learn animal",
        "learn animals",
    )

    STOP_TRIGGERS = (
        "وقف",
        "خلاص",
        "انهاء",
        "انهي",
        "توقف",
        "رجع للدرده",
        "رجع للدردشة",
        "stop lesson",
    )

    def __init__(self) -> None:
        self.active: bool = False
        self.topic_i: int = 0
        self.stage: str = "ask"  # ask | hint | want_more
        self.kid_name: str = "صديقي"

    def in_session(self) -> bool:
        return bool(self.active)

    def maybe_start(self, user_text: str, kid_name: str = "صديقي") -> Optional[str]:
        t = _norm(user_text)
        if any(_norm(k) in t for k in self.START_TRIGGERS):
            self.active = True
            self.topic_i = 0
            self.stage = "ask"
            self.kid_name = kid_name or "صديقي"
            return _fmt(f"تمام {self.kid_name} خلينا نبدي حصة الحيوانات {TOPICS[self.topic_i].q}")
        return None

    def handle(self, user_text: str, kid_name: str = "صديقي") -> Optional[str]:
        if not self.active:
            return None

        self.kid_name = kid_name or self.kid_name
        t = _norm(user_text)

        if any(_norm(k) in t for k in self.STOP_TRIGGERS):
            self.active = False
            return _fmt(f"تمام {self.kid_name} رجعنا للدردشة" , emotion="normal", motion=0)

        topic = TOPICS[self.topic_i]

        if self.stage == "ask":
            if any(k in t for k in topic.correct_any):
                self.stage = "want_more"
                return _fmt(f"احسنت {self.kid_name} {topic.explain} تحب سؤال ثاني")
            if any(k in t for k in topic.partial_any):
                self.stage = "hint"
                return _fmt(f"اي ممكن هذا سبب بس اكو سبب اهم {topic.hint_q}")
            # unknown
            self.stage = "hint"
            return _fmt(f"قريب من الاجابه خليني اعطيك تلميح {topic.hint_q}")

        if self.stage == "hint":
            # after hint, accept broader breathing/energy/water keywords
            if any(k in t for k in topic.correct_any) or any(x in t for x in ("رئ", "تنفس", "طاق", "مي", "ماء", "سبح")):
                self.stage = "want_more"
                return _fmt(f"تمام {self.kid_name} {topic.explain} تحب سؤال ثاني")
            # repeat explanation softly
            self.stage = "want_more"
            return _fmt(f"ولا يهمك {self.kid_name} {topic.explain} تحب سؤال ثاني")

        if self.stage == "want_more":
            if any(x in t for x in ("اي", "نعم", "اجل", "اكيد", "اريد", "yes")):
                self.topic_i = (self.topic_i + 1) % len(TOPICS)
                self.stage = "ask"
                return _fmt(f"حلو {self.kid_name} السؤال الجديد {TOPICS[self.topic_i].q}")
            # end lesson politely
            self.active = False
            return _fmt(f"تمام {self.kid_name} اذا تحب نرجع للدردشة او ندرس نباتات كلي")

        # fallback reset
        self.active = False
        return None
