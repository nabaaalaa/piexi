"""
learn_plants.py
Deterministic science warm-up lesson (plants) for children.

Goal:
- Fun, short, teacher-style Q&A.
- Keyword-based checking (no external dependencies).
- Returns formatted strings: "<text>" (Teacher) <0>

This module is designed to be called from Robot_paixi.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import re


def _norm(text: str) -> str:
    t = (text or "").strip().lower()
    t = re.sub(r"[\u064B-\u065F]", "", t)  # tashkeel
    t = t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    t = t.replace("ة", "ه")
    t = t.replace("ى", "ي")
    return t


def _fmt(text: str, emotion: str = "Teacher", motion: int = 0) -> str:
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
        q="ليش النبات يحتاج ضوء الشمس",
        correct_any=["يصنع غذ", "يبني غذ", "يمتص ضوء", "طاقة", "تمثيل", "ضوئي"],
        partial_any=["ينمو", "يكبر"],
        hint_q="منين النبات يجيب اكله اذا ما ياكل مثلنا",
        explain="النبات يسوي غذائه بنفسه باستخدام ضوء الشمس والماء والهواء هذا اسمه التمثيل الضوئي",
    ),
    _Topic(
        q="شنو فايدة الجذور بالنبات",
        correct_any=["يمتص", "ماء", "املاح", "يثبت", "تثبيت"],
        partial_any=["يطول"],
        hint_q="اذا سحبنا النبات من التربه شنو الي يظل داخل الارض",
        explain="الجذور تمتص الماء والاملاح من التربه وتثبت النبات حتى ما يطيح",
    ),
    _Topic(
        q="ليش اغلب اوراق النبات لونها اخضر",
        correct_any=["كلوروف", "كلوروفيل", "يمتص", "ضوء"],
        partial_any=["صبغه"],
        hint_q="النبات بي ماده تمسك ضوء الشمس داخل الورقه شنو اسمها",
        explain="اللون الاخضر بسبب ماده اسمها كلوروفيل تساعد الورقه تمسك ضوء الشمس حتى يصير التمثيل الضوئي",
    ),
]


class PlantLessonAgent:
    START_TRIGGERS = (
        "تعلم النباتات",
        "درس النباتات",
        "حصة النباتات",
        "نبدأ نباتات",
        "نبلش نباتات",
        "نباتات",
        "learn plant",
        "learn plants",
    )

    STOP_TRIGGERS = (
        "وقف",
        "خلاص",
        "انهاء",
        "توقف",
        "رجع للدرده",
        "رجع للدردشة",
        "stop lesson",
    )

    def __init__(self) -> None:
        self.active: bool = False
        self.topic_i: int = 0
        self.stage: str = "ask"
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
            return _fmt(f"تمام {self.kid_name} خلينا نبدي حصة النباتات {TOPICS[self.topic_i].q}")
        return None

    def handle(self, user_text: str, kid_name: str = "صديقي") -> Optional[str]:
        if not self.active:
            return None

        self.kid_name = kid_name or self.kid_name
        t = _norm(user_text)

        if any(_norm(k) in t for k in self.STOP_TRIGGERS):
            self.active = False
            return _fmt(f"تمام {self.kid_name} رجعنا للدردشة", emotion="normal", motion=0)

        topic = TOPICS[self.topic_i]

        if self.stage == "ask":
            if any(k in t for k in topic.correct_any):
                self.stage = "want_more"
                return _fmt(f"احسنت {self.kid_name} {topic.explain} تحب سؤال ثاني")
            if any(k in t for k in topic.partial_any):
                self.stage = "hint"
                return _fmt(f"اي هذا جزء من الجواب بس خليني اعطيك تلميح {topic.hint_q}")
            self.stage = "hint"
            return _fmt(f"قريب من الاجابه تلميح صغير {topic.hint_q}")

        if self.stage == "hint":
            if any(k in t for k in topic.correct_any) or any(x in t for x in ("غذا", "اكل", "ماء", "املاح", "ضوء", "كلورو")):
                self.stage = "want_more"
                return _fmt(f"تمام {self.kid_name} {topic.explain} تحب سؤال ثاني")
            self.stage = "want_more"
            return _fmt(f"ولا يهمك {self.kid_name} {topic.explain} تحب سؤال ثاني")

        if self.stage == "want_more":
            if any(x in t for x in ("اي", "نعم", "اجل", "اكيد", "اريد", "yes")):
                self.topic_i = (self.topic_i + 1) % len(TOPICS)
                self.stage = "ask"
                return _fmt(f"حلو {self.kid_name} السؤال الجديد {TOPICS[self.topic_i].q}")
            self.active = False
            return _fmt(f"تمام {self.kid_name} اذا تحب نرجع للدردشة او ندرس حيوانات كلي")

        self.active = False
        return None
