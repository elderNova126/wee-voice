#!/usr/bin/env python
"""
Seed or update public demo agents for the WeeVoice platform.

This helper script ensures that the default demo user and public agents exist
with the expected configuration. It is safe to run multiple times; existing
records will be updated in place.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv
from sqlalchemy.orm import Session
from textwrap import dedent


# Ensure we can import the backend package when the script is executed directly
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Load environment variables if a backend .env file is present
env_path = BACKEND_DIR / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # Fall back to repository root .env if available
    root_env = BACKEND_DIR.parent / ".env"
    if root_env.exists():
        load_dotenv(root_env)

from app.core.security import get_password_hash
from app.models import SubscriptionTier, User, VoiceAgent  # noqa: E402
from app.models.database import SessionLocal  # noqa: E402


FRENCH_DEMO_PROMPT = dedent(
    """
    Tu es un assistant vocal francophone chaleureux et professionnel qui aide
    les visiteurs à découvrir WeeVoice. Ton objectif est d'expliquer la
    plateforme, de répondre aux questions fréquentes et d'orienter la
    conversation vers une démonstration ou une prise de contact humaine.

    Directives principales :
    - Réponds toujours en français dans un ton naturel et dynamique.
    - Mets en avant la faible latence, l'intégration CRM et la conformité de la plateforme.
    - Pose des questions ouvertes pour comprendre le besoin (support client, vente, service interne, etc.).
    - Termine par une proposition d'étape suivante concrète (prise de rendez-vous, envoi d'informations, accès au tableau de bord).
    - Si l'utilisateur pose une question technique, donne une réponse concise puis propose de transférer à l'équipe produit.
    """
).strip()

REAL_ESTATE_PROMPT = dedent(
    """
    Tu es Lina Haddad, consultante senior en découverte immobilière pour Horizon Properties,
    un cabinet qui accompagne des clients francophones souhaitant investir à Dubaï. Tu contactes
    des leads entrants ou dormants pour comprendre leur projet et les qualifier avant de les passer
    à un conseiller agréé.

    Objectifs essentiels :
    - Conduire un entretien de découverte complet : motivation pour Dubaï, état d’avancement du projet,
      connaissance de la ville, offres déjà reçues (par qui, sur quels projets et pourquoi elles n’ont pas abouti),
      budget disponible, personnes impliquées dans la décision, et niveau d’engagement si le bien idéal est trouvé.
    - Dans les premières secondes, désamorcer les objections classiques (« Je n’ai pas le temps », « Je ne suis plus intéressé »,
      « Rappelez-moi plus tard »). Réponds avec empathie, un rappel de valeur en moins de 20 secondes, puis poursuis ou
      propose un créneau précis.
    - Ne propose jamais de programmes concrets, de prix ou d’incitations. Ton rôle est d’écouter, clarifier et garantir
      un suivi personnalisé avec un conseiller humain.

    Déroulé recommandé :
    1. Vérifie si le moment est opportun ; sinon planifie un rappel précis.
    2. Demande ce qui les attire actuellement à Dubaï ou ce qui a évolué depuis le dernier échange.
    3. Explore leur connaissance de la ville ou des quartiers ; apporte des précisions uniquement si on te les demande.
    4. Parle des offres déjà examinées, des interlocuteurs et des raisons du blocage.
    5. Identifie la structure d’investissement (seul, en couple, en famille, avec associés) et les décideurs.
    6. Recueille la fourchette budgétaire et la devise ; vérifie s’il y a besoin de financement.
    7. Comprends l’échéance et ce qui déclencherait un engagement.
    8. Utilise l’écoute active, fais des synthèses intermédiaires et valide que tu as bien compris.
    9. Conclus par un récapitulatif clair et une prochaine étape définie (rendez-vous expert, envoi d’informations ciblées, rappel programmé).

    Règles de conformité :
    - Reste professionnelle, concise et conversationnelle, en français naturel ; adapte ton énergie à celle du prospect.
    - Si l’on insiste pour obtenir des offres ou des prix, explique qu’un conseiller agréé préparera des options personnalisées après la découverte.
    - Si la personne refuse catégoriquement, remercie-la, note le désintérêt et rappelle qu’elle peut revenir vers toi à tout moment.
    """
).strip()

PUBLIC_AGENTS: List[Dict[str, object]] = [
    {
        "name": "Assistant Démo Français",
        "description": "Agent de démonstration en français pour présenter WeeVoice.",
        "language": "fr-FR",
        "voice_gender": "male",
        "voice_id": "Charon",
        "system_prompt": FRENCH_DEMO_PROMPT,
        "greeting": (
            "Bonjour, ici l'assistant WeeVoice. Je suis là pour vous montrer comment notre plateforme "
            "peut gérer des conversations vocales en temps réel. Comment puis-je vous aider ?"
        ),
        "model_name": "gemini-2.5-flash-native-audio-preview-09-2025",
        "temperature": "0.7",
        "max_tokens": 1000,
        "is_public": True,
    },
    {
        "name": "Dubai Real Estate Discovery",
        "description": "Analyse et qualification en français des leads immobiliers intéressés par Dubaï.",
        "language": "fr-FR",
        "voice_gender": "female",
        "voice_id": "Kore",
        "system_prompt": REAL_ESTATE_PROMPT,
        "greeting": (
            "Bonjour, ici Lina du pôle découverte Horizon Properties à Dubaï. "
            "Merci de prendre mon appel. J’aimerais comprendre rapidement où vous en êtes pour "
            "vous orienter vers le bon conseiller. Est-ce que c’est un bon moment ou souhaitiez-vous "
            "que nous fixions un créneau précis ?"
        ),
        "model_name": "gemini-2.5-flash-native-audio-preview-09-2025",
        "temperature": "0.7",
        "max_tokens": 1000,
        "is_public": True,
    },
]


def ensure_demo_user(session: Session) -> User:
    """Create the default demo user if it does not already exist."""
    user = session.query(User).filter(User.email == "demo@voiceagent.com").first()
    if user:
        return user

    user = User(
        email="demo@voiceagent.com",
        full_name="Demo User",
        hashed_password=get_password_hash("password123"),
        subscription_tier=SubscriptionTier.FREE,
        is_active=True,
        is_superuser=True,
        is_approved=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    print(f"Created demo user with id {user.id}")
    return user


def upsert_agent(session: Session, user: User, config: Dict[str, object]) -> VoiceAgent:
    """Create or update a public agent for the given user."""
    agent = (
        session.query(VoiceAgent)
        .filter(VoiceAgent.user_id == user.id, VoiceAgent.name == config["name"])
        .first()
    )

    fields = {
        "description": config.get("description"),
        "language": config.get("language", "fr-FR"),
        "voice_gender": config.get("voice_gender", "male"),
        "voice_id": config.get("voice_id"),
        "system_prompt": config.get("system_prompt"),
        "greeting": config.get("greeting"),
        "model_name": config.get("model_name", "gemini-2.5-flash-native-audio-preview-09-2025"),
        "temperature": config.get("temperature", "0.7"),
        "max_tokens": config.get("max_tokens", 1000),
        "is_public": config.get("is_public", True),
        "is_active": True,
        "tools_enabled": config.get("tools_enabled", []),
    }

    if agent:
        updated = False
        for key, value in fields.items():
            if getattr(agent, key) != value:
                setattr(agent, key, value)
                updated = True
        if updated:
            session.add(agent)
            session.commit()
            session.refresh(agent)
            print(f"Updated agent '{agent.name}' (id {agent.id})")
        else:
            print(f"Agent '{agent.name}' (id {agent.id}) already up to date")
    else:
        agent = VoiceAgent(user_id=user.id, name=config["name"], **fields)
        session.add(agent)
        session.commit()
        session.refresh(agent)
        print(f"Created agent '{agent.name}' (id {agent.id})")

    return agent


def main() -> None:
    session = SessionLocal()
    try:
        user = ensure_demo_user(session)
        for agent_config in PUBLIC_AGENTS:
            upsert_agent(session, user, agent_config)
        print("✅ Public agents seeded successfully.")
    finally:
        session.close()


if __name__ == "__main__":
    main()

