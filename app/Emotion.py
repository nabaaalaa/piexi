"""
Emotion.py
- Uses a dedicated OpenAI API key (env var: OPENAI_API_KEY_EMOTION)
- Classifies a child's message into ONE emotion label.

Allowed labels:
normal, happy, sad, encourage, fraid, Gratitude, Teacher, celebrate, frustration
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Literal

from openai import OpenAI


EmotionLabel = Literal[
    "normal",
    "happy",
    "sad",
    "encourage",
    "fraid",
    "Gratitude",
    "Teacher",
    "celebrate",
    "frustration",
]


@dataclass
class EmotionResult:
    emotion: EmotionLabel
    brief_reason: str


class EmotionAgent:
    """
    An emotion classifier specialized for ages 5-12.
    It ONLY returns an emotion label + a short reason.
    """

    def __init__(
        self,
        model: str = "gpt-5.2",
        api_key_env: str = "OPENAI_API_KEY_EMOTION",
    ) -> None:
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise RuntimeError(
                f"Missing {api_key_env}. Set it as an environment variable for Emotion.py."
            )

        # Optional debug to ensure the correct file is loaded
        if os.getenv("PAIXI_DEBUG") == "1":
            print("Loaded Emotion.py from:", __file__)

        self.client = OpenAI(api_key=api_key)
        self.model = model

        self._allowed = {
            "normal",
            "happy",
            "sad",
            "encourage",
            "fraid",
            "Gratitude",
            "Teacher",
            "celebrate",
            "frustration",
        }

    def _extract_json(self, raw: str) -> dict:
        raw = (raw or "").strip()
        if not raw:
            return {"emotion": "normal", "brief_reason": "Empty output."}

        # direct JSON
        try:
            return json.loads(raw)
        except Exception:
            pass

        # extract first {...}
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except Exception:
                pass

        # fallback: find emotion keyword
        m = re.search(r"(normal|happy|sad|encourage|fraid|Gratitude|Teacher|celebrate|frustration)", raw)
        emo = m.group(1) if m else "normal"
        return {"emotion": emo, "brief_reason": "Fallback parse."}

    def analyze(self, user_text: str) -> EmotionResult:
        user_text = (user_text or "").strip()

        instructions = (
            "You are an emotion classifier for a friendly robot talking to children (5-12).\n"
            "Return STRICT JSON ONLY (no extra text) with keys: emotion, brief_reason.\n"
            "emotion must be exactly one of:\n"
            "normal, happy, sad, encourage, fraid, Gratitude, Teacher, celebrate, frustration\n"
            "brief_reason must be short (max 120 chars).\n\n"
            "Rules:\n"
            "- normal: everyday chat / neutral.\n"
            "- happy: excitement, good news.\n"
            "- sad: sadness, loss, needs comfort.\n"
            "- encourage: child asks for motivation / wants to try again.\n"
            "- fraid: fear or worry.\n"
            "- Gratitude: thanks.\n"
            "- Teacher: child asks to learn / asks a question.\n"
            "- celebrate: solved something / success.\n"
            "- frustration: upset because wrong/failed.\n"
        )

        # IMPORTANT: no response_format, no structured params
        resp = self.client.responses.create(
            model=self.model,
            instructions=instructions,
            input=user_text,
        )

        raw = getattr(resp, "output_text", "") or ""
        data = self._extract_json(raw)

        emo = str(data.get("emotion", "normal")).strip()
        reason = (str(data.get("brief_reason", "")).strip() or "—")[:120]

        if emo not in self._allowed:
            emo = "normal"

        return EmotionResult(emotion=emo, brief_reason=reason)
