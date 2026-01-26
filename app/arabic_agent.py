"""
arabic_agent.py
Deterministic Arabic spelling lesson agent for children (age 5-12).

Behavior:
- When Arabic lesson starts (triggered by specific phrases), the agent selects a simple word
  (default: "أرنب") and teaches spelling letter-by-letter.
- For each target letter, the agent asks the child to repeat the letter name (e.g., "باء").
- If correct: "احسنت" with (celebrate) and motion sequence <1><1><2><2><0>
- If wrong: "خطأ، كرر محاولة مرة اخرى" with (frustration) and motion sequence <3><4>
- If close: "انت قريب من الاجابة" with (frustration) and <0>
- After finishing letters, the agent asks the child to say the full word, then ends the lesson.

This module is designed to be called from Robot_paixi.py.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# ----------------------------
# Small Arabic normalization
# ----------------------------
_AR_DIACRITICS = re.compile(r"[\u064B-\u065F\u0670\u06D6-\u06ED]")
_AR_PUNCT = re.compile(r"[^\u0600-\u06FF0-9A-Za-z\s]+")


def _norm_ar(s: str) -> str:
    s = (s or "").strip()
    # remove quotes
    s = s.strip('"\'')

    # remove tatweel
    s = s.replace("ـ", "")

    # remove diacritics
    s = _AR_DIACRITICS.sub("", s)

    # normalize alifs / hamza forms lightly
    s = s.replace("إ", "ا").replace("أ", "ا").replace("آ", "ا")

    # normalize taa marbuta
    s = s.replace("ة", "ه")  # for matching in speech-to-text cases

    # remove punctuation
    s = _AR_PUNCT.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


@dataclass
class LessonState:
    active: bool = False
    word: str = "أرنب"
    letters: List[str] = None  # type: ignore
    i: int = 0
    stage: str = "letters"  # "letters" or "word"
    kid_name: str = "صديقي"

    def __post_init__(self) -> None:
        if self.letters is None:
            self.letters = []


class ArabicLessonAgent:
    """
    Deterministic spelling lesson.
    """

    # triggers that mean "start Arabic lesson"
    START_TRIGGERS = (
        "حصة العربية",
        "حصة اللغه العربية",
        "حصة اللغة العربية",
        "درس عربي",
        "درس العربية",
        "نبدأ عربي",
        "نبدي عربي",
        "ابدأ عربي",
        "ابدي عربي",
        "حصة عربي",
    )

    # a small list of simple words (you can extend later)
    WORDS = ["أرنب", "بطة", "تفاحة", "قلم"]

    # letter -> (name, accepted_variants, close_variants)
    # NOTE: Accepted/close are normalized with _norm_ar
    LETTER_RULES: Dict[str, Tuple[str, List[str], List[str]]] = {
        "ا": ("ألف", ["الف", "ا", "الِف", "ألف"], ["الفه", "الـف"]),
        "ب": ("باء", ["باء", "با", "ب"], ["با", "بي"]),
        "ت": ("تاء", ["تاء", "تا", "ت"], ["تا", "تي"]),
        "ث": ("ثاء", ["ثاء", "ثا", "ث"], ["ثا"]),
        "ج": ("جيم", ["جيم", "جي", "ج"], ["جي"]),
        "ح": ("حاء", ["حاء", "حا", "ح"], ["حا"]),
        "خ": ("خاء", ["خاء", "خا", "خ"], ["خا"]),
        "د": ("دال", ["دال", "دا", "د"], ["دا"]),
        "ذ": ("ذال", ["ذال", "ذا", "ذ"], ["ذا"]),
        "ر": ("راء", ["راء", "را", "ر"], ["را"]),
        "ز": ("زاي", ["زاي", "زا", "ز"], ["زا"]),
        "س": ("سين", ["سين", "سي", "س"], ["سي"]),
        "ش": ("شين", ["شين", "شي", "ش"], ["شي"]),
        "ص": ("صاد", ["صاد", "صا", "ص"], ["صا"]),
        "ض": ("ضاد", ["ضاد", "ضا", "ض"], ["ضا"]),
        "ط": ("طاء", ["طاء", "طا", "ط"], ["طا"]),
        "ظ": ("ظاء", ["ظاء", "ظا", "ظ"], ["ظا"]),
        "ع": ("عين", ["عين", "عي", "ع"], ["عي"]),
        "غ": ("غين", ["غين", "غي", "غ"], ["غي"]),
        "ف": ("فاء", ["فاء", "فا", "ف"], ["فا"]),
        "ق": ("قاف", ["قاف", "قا", "ق"], ["قا"]),
        "ك": ("كاف", ["كاف", "كا", "ك"], ["كا"]),
        "ل": ("لام", ["لام", "لا", "ل"], ["لا"]),
        "م": ("ميم", ["ميم", "مي", "م"], ["مي"]),
        "ن": ("نون", ["نون", "نو", "ن"], ["نو"]),
        "ه": ("هاء", ["هاء", "ها", "ه"], ["ها"]),
        "و": ("واو", ["واو", "وا", "و"], ["وا"]),
        "ي": ("ياء", ["ياء", "يا", "ي"], ["يا"]),
        # taa marbuta shown as "ه" in normalization
        "ة": ("تاء مربوطة", ["تاء مربوطة", "ه", "ة", "اا", "آآ", "ااا"], ["ا", "aa"]),
        "ء": ("همزة", ["همزة", "ء"], ["ا"]),
        "أ": ("ألف", ["الف", "ألف", "ا"], ["الف"]),
        "إ": ("ألف", ["الف", "ألف", "ا"], ["الف"]),
        "آ": ("ألف", ["الف", "ألف", "ا"], ["الف"]),
    }

    def __init__(self) -> None:
        self.state = LessonState()

    # ----------------------------
    # Public API for Robot_paixi
    # ----------------------------
    def in_session(self) -> bool:
        return bool(self.state.active)

    def maybe_start(self, user_text: str, kid_name: str = "صديقي") -> Optional[str]:
        """
        If user_text contains a start trigger, start lesson and return first prompt.
        Otherwise return None.
        """
        t = _norm_ar(user_text)
        if not t:
            return None
        for trig in self.START_TRIGGERS:
            if _norm_ar(trig) in t:
                return self.start(kid_name=kid_name)
        return None

    def start(self, word: str = "أرنب", kid_name: str = "صديقي") -> str:
        self.state.active = True
        self.state.word = word
        self.state.kid_name = kid_name or "صديقي"
        self.state.letters = self._split_letters(word)
        self.state.i = 0
        self.state.stage = "letters"

        # first letter prompt
        letter = self.state.letters[self.state.i]
        name = self._letter_name(letter)
        msg = (
            "سنبدأ اليوم بحصة اللغة العربية. "
            "سنتعلم تهجئة الأحرف. "
            f"اخترنا كلمة {word}. "
            f"الحرف الأول هو {letter}. قل بعدي {name}."
        )
        return self._format(msg, "teacher", [0])

    def handle(self, user_text: str) -> Optional[str]:
        """
        Handle a user reply during a lesson.
        Returns formatted agent reply, or None if not in lesson.
        """
        if not self.state.active:
            return None

        t = _norm_ar(user_text)
        if not t:
            # repeat current prompt
            return self._repeat_prompt()

        if self.state.stage == "letters":
            return self._handle_letter_step(t)

        if self.state.stage == "word":
            return self._handle_word_step(t)

        # unknown stage, reset safely
        self.state.active = False
        return None

    # ----------------------------
    # Internal logic
    # ----------------------------
    def _split_letters(self, word: str) -> List[str]:
        # Keep Arabic letters; ignore spaces/punct
        letters = [ch for ch in word if re.match(r"[\u0600-\u06FF]", ch)]
        return letters or ["ا"]

    def _letter_name(self, letter: str) -> str:
        # normalize for mapping keys
        if letter in self.LETTER_RULES:
            return self.LETTER_RULES[letter][0]
        # normalize hamza/alifs
        if letter in ("أ", "إ", "آ"):
            return "ألف"
        if letter == "ة":
            return "تاء مربوطة"
        # fallback
        return "هذا الحرف"

    def _judge_letter(self, normalized_answer: str, letter: str) -> str:
        """
        Returns: "correct" | "close" | "wrong"
        """
        # map special letters to keys used in rules
        rule_key = letter
        if rule_key in ("أ", "إ", "آ"):
            rule_key = "ا"
        if rule_key == "ة":
            rule_key = "ة"

        name, accepted, close = self.LETTER_RULES.get(rule_key, (self._letter_name(letter), [], []))

        ans = normalized_answer

        # also accept if child sent the letter itself
        if ans == _norm_ar(letter):
            return "correct"

        if ans in [_norm_ar(x) for x in accepted]:
            return "correct"

        # close answers
        if ans in [_norm_ar(x) for x in close]:
            return "close"

        # heuristic: same starting letter
        if ans and _norm_ar(letter) and ans[0] == _norm_ar(letter)[0]:
            return "close"

        # heuristic: if they said the name but missing last char
        acc_norm = [_norm_ar(x) for x in accepted]
        if any(a.startswith(ans) or ans.startswith(a) for a in acc_norm if a and ans):
            return "close"

        return "wrong"

    def _repeat_prompt(self) -> str:
        if self.state.stage == "letters":
            letter = self.state.letters[self.state.i]
            name = self._letter_name(letter)
            msg = f"قل بعدي {name}."
            return self._format(msg, "teacher", [0])
        else:
            msg = f"قل بعدي {self.state.word}."
            return self._format(msg, "teacher", [0])

    def _handle_letter_step(self, normalized_answer: str) -> str:
        letter = self.state.letters[self.state.i]
        name = self._letter_name(letter)
        verdict = self._judge_letter(normalized_answer, letter)

        if verdict == "correct":
            # move to next letter or to word stage
            self.state.i += 1

            if self.state.i < len(self.state.letters):
                next_letter = self.state.letters[self.state.i]
                next_name = self._letter_name(next_letter)
                msg = (
                    "احسنت. "
                    f"الحرف التالي هو {next_letter}. "
                    f"قل بعدي {next_name}."
                )
                return self._format(msg, "celebrate", [1, 1, 2, 2, 0])

            # finished letters -> ask for full word
            self.state.stage = "word"
            spelled = " ".join(self.state.letters)
            msg = (
                "احسنت. "
                f"الآن لنجمع الأحرف {spelled} تصبح {self.state.word}. "
                f"قل بعدي {self.state.word}."
            )
            return self._format(msg, "celebrate", [1, 1, 2, 2, 0])

        if verdict == "close":
            msg = f"انت قريب من الاجابة. حاول مرة اخرى. قل {name}."
            return self._format(msg, "frustration", [0])

        # wrong
        msg = f"خطأ، كرر محاولة مرة اخرى. قل بعدي {name}."
        return self._format(msg, "frustration", [3, 4])

    def _handle_word_step(self, normalized_answer: str) -> str:
        target = _norm_ar(self.state.word)
        if normalized_answer == target or normalized_answer.replace(" ", "") == target.replace(" ", ""):
            # finish lesson
            self.state.active = False
            msg = "انت رائع احسنت حقا وهنا تنتهي حصتنا لليوم"
            return self._format(msg, "happy", [0])

        # close: contains most letters
        if len(set(normalized_answer)) >= max(1, len(set(target)) - 1):
            msg = f"انت قريب من الاجابة. قل بعدي {self.state.word}."
            return self._format(msg, "frustration", [0])

        msg = f"خطأ، كرر محاولة مرة اخرى. قل بعدي {self.state.word}."
        return self._format(msg, "frustration", [3, 4])

    def _format(self, text: str, emotion: str, motions: List[int]) -> str:
        # format motions as <m><m>...
        motion_part = "".join(f"<{int(m)}>" for m in motions) if motions else "<0>"
        return f"\"{text.strip()}\" ({emotion}) {motion_part}"
