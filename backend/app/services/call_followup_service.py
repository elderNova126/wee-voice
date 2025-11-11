"""
Utilities for extracting follow-up tags from call action items.
"""
from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

from app.models.call import Call


EMAIL_KEYWORDS = (
    "email",
    "mail",
    "courriel",
    "courrier électronique",
    "e-mail",
)

MESSAGE_KEYWORDS = (
    "message",
    "sms",
    "texto",
    "text",
    "whatsapp",
    "signal",
    "telegram",
)

CALLBACK_KEYWORDS = (
    "callback",
    "follow-up",
    "follow up",
    "rappel",
    "rappeler",
    "call back",
    "relancer",
)

MEETING_KEYWORDS = (
    "rendez-vous",
    "rdv",
    "meeting",
    "appointment",
    "visio",
    "call",
    "conférence",
)

DOCUMENT_KEYWORDS = (
    "document",
    "brochure",
    "pdf",
    "fichier",
    "deck",
    "presentation",
    "présentation",
)

QUOTE_KEYWORDS = (
    "devis",
    "quote",
    "offre",
    "pricing",
    "tarif",
    "tarification",
    "proposition",
)

DEMO_KEYWORDS = (
    "demo",
    "démonstration",
    "essai",
    "trial",
)


def _safe_iter(items: Optional[Sequence[str]]) -> Iterable[str]:
    if not items:
        return []
    return (str(item) for item in items if item)


def derive_action_tags(
    call: Call,
    action_items: Optional[Sequence[str]] = None,
) -> List[str]:
    """
    Determine follow-up tags for a call based on action items and call metadata.
    """
    tags: List[str] = []

    def add_tag(label: str) -> None:
        if label not in tags:
            tags.append(label)

    # Action items-derived tags
    for item in _safe_iter(action_items):
        lower_item = item.lower()

        if any(keyword in lower_item for keyword in EMAIL_KEYWORDS):
            add_tag("send email request")

        if any(keyword in lower_item for keyword in MESSAGE_KEYWORDS):
            add_tag("send message request")

        if any(keyword in lower_item for keyword in CALLBACK_KEYWORDS):
            add_tag("Callback requested")

        if any(keyword in lower_item for keyword in MEETING_KEYWORDS):
            add_tag("Schedule meeting")

        if any(keyword in lower_item for keyword in DOCUMENT_KEYWORDS):
            add_tag("Share document")

        if any(keyword in lower_item for keyword in QUOTE_KEYWORDS):
            add_tag("Send quote")

        if any(keyword in lower_item for keyword in DEMO_KEYWORDS):
            add_tag("Book demo")

    # Call-level cues
    if getattr(call, "callback_requested", False):
        add_tag("Callback requested")

    if getattr(call, "callback_reason", None):
        reason = str(call.callback_reason).lower()
        if any(keyword in reason for keyword in EMAIL_KEYWORDS):
            add_tag("send email request")
        if any(keyword in reason for keyword in MESSAGE_KEYWORDS):
            add_tag("send message request")

    # Fallback: surface raw action items as contextual tags (trimmed)
    for item in _safe_iter(action_items):
        normalized = item.strip()
        if not normalized:
            continue
        # Avoid duplicating generated tags for short keywords
        if len(normalized) > 60:
            normalized = f"{normalized[:57].rstrip()}..."
        annotated = f"Action: {normalized}"
        add_tag(annotated)

    return tags


def update_call_follow_up_data(
    call: Call,
    action_items: Optional[Sequence[str]] = None,
) -> None:
    """
    Persist action items and corresponding tags on the call object.
    """
    if action_items is not None:
        # Ensure JSON-serializable list
        call.action_items = list(_safe_iter(action_items))

    effective_items = call.action_items or []
    call.action_tags = derive_action_tags(call, effective_items)

