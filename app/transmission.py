"""
transmission.py
- Uses a dedicated OpenAI API key (env var: OPENAI_API_KEY_MOTION)
- Decides robot motion as integers only.

Motion commands:
0 stop, 1 forward, 2 back, 3 right, 4 left
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Literal

from openai import OpenAI


MotionInt = Literal[0, 1, 2, 3, 4]


@dataclass
class MotionDecision:
    primary: MotionInt
    # Optional short "spontaneous" sequence, still integers only (e.g., [1,2,1,2,1,2,0])
    sequence: List[MotionInt]


class MotionAgent:
    """
    Motion decision logic:
    - If user asks for a move: output that move (1-4) else 0.
    - Spontaneous sequences can be triggered by events (emotion/quiz result).
    """

    def __init__(
        self,
        model: str = "gpt-5.2",
        api_key_env: str = "OPENAI_API_KEY_MOTION",
    ) -> None:
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise RuntimeError(
                f"Missing {api_key_env}. Set it as an environment variable for transmission.py."
            )
        self.client = OpenAI(api_key=api_key)
        self.model = model

    # ---------- Deterministic keyword routing (fast + safe) ----------
    @staticmethod
    def _keyword_motion(text: str) -> Optional[MotionInt]:
        t = (text or "").strip().lower()

        # Arabic
        if re.search(r"\b(توقف|ستوب|وقف)\b", t):
            return 0
        if re.search(r"\b(امام|قدام|للأمام|لل امام|forward)\b", t):
            return 1
        if re.search(r"\b(وراء|للخلف|خلف|backward|back)\b", t):
            return 2
        if re.search(r"\b(يمين|right)\b", t):
            return 3
        if re.search(r"\b(يسار|left)\b", t):
            return 4

        return None

    # ---------- Spontaneous sequences (integers only) ----------
    @staticmethod
    def spontaneous_for_event(event: str) -> List[MotionInt]:
        """
        event can be:
        - "very_happy"
        - "sad"
        - "wrong_answer"
        """
        if event == "very_happy":
            # forward/back 3 times then stop
            seq: List[MotionInt] = [1, 2, 1, 2, 1, 2, 0]
            return seq
        if event == "sad":
            # back slowly then stop (represented as: back then stop)
            return [2, 0]
        if event == "wrong_answer":
            # right/left 5 times then stop
            seq2: List[MotionInt] = [3, 4, 3, 4, 3, 4, 3, 4, 3, 4, 0]
            return seq2
        return [0]

    def decide(self, user_text: str, *, default_state: MotionInt = 0) -> MotionDecision:
        """
        Returns primary motion command and optional sequence.
        By default, keep robot at 0 unless user explicitly requests movement.
        """
        kw = self._keyword_motion(user_text)
        if kw is not None:
            return MotionDecision(primary=kw, sequence=[kw])

        # If no explicit movement request, keep default (usually 0).
        return MotionDecision(primary=default_state, sequence=[default_state])
