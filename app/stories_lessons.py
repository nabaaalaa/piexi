"""stories_lessons.py
Subject: سماع القصص
Not available in this simplified curriculum.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from lesson_base import clean_arabic_plain

def start_lesson(profile: Dict[str, Any], lesson_no: int) -> Tuple[str, Dict[str, Any], str]:
    return clean_arabic_plain("هذا غير متوفر الان"), {}, "Teacher"

def handle_turn(profile: Dict[str, Any], lesson_no: int, user_text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool, str]:
    return clean_arabic_plain("هذا غير متوفر الان"), dict(state or {}), True, "Teacher"
