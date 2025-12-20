"""
Prompt templates for voice and text chat agents.

This module provides reusable prompt templates that ensure consistent
conversation style and behavior across both voice calls and text chat.
"""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent


def load_prompt(filename: str) -> str:
    """Load a prompt template from file"""
    prompt_path = PROMPTS_DIR / filename
    if prompt_path.exists():
        return prompt_path.read_text(encoding='utf-8')
    return ""

