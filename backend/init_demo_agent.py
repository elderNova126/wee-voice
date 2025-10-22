#!/usr/bin/env python3
"""
Initialize demo agent in database
Run this to create a public demo agent for the demo page
"""

from sqlalchemy.orm import Session
from app.models.database import SessionLocal
from app.models import User, VoiceAgent
from dotenv import load_dotenv

load_dotenv()

def init_demo_agent():
    """Create demo user and agent if they don't exist"""
    db: Session = SessionLocal()
    
    try:
        # Check if demo user exists
        user = db.query(User).filter(User.email == "demo@voiceagent.com").first()
        
        if not user:
            print("❌ Demo user not found!")
            print("Please run the SQL schema first:")
            print("   database/supabase_schema_simple.sql")
            return False
        
        print(f"✅ Found demo user: {user.email}")
        
        # Check if public demo agent exists
        agent = db.query(VoiceAgent).filter(
            VoiceAgent.is_public == True,
            VoiceAgent.is_active == True
        ).first()
        
        if agent:
            print(f"✅ Public demo agent already exists: {agent.name}")
            print(f"   Agent ID: {agent.id}")
            print(f"   Language: {agent.language}")
            return True
        
        # Create French demo agent
        print("📝 Creating French demo agent...")
        
        french_agent = VoiceAgent(
            user_id=user.id,
            name="Assistant Démo Français",
            description="Agent de démonstration en français pour tester la plateforme",
            language="fr-FR",
            voice_id="fr-FR-Neural2-A",
            system_prompt="""Vous êtes un assistant vocal intelligent et serviable de Weedoo, qui répond toujours en français, de manière naturelle et amicale.

Tu peux aider avec:
- Répondre à des questions générales
- Avoir des conversations naturelles
- Fournir des informations
- Être courtois et professionnel

Reste toujours poli, clair et concis dans tes réponses.""",
            greeting="Bonjour, je suis un assistant vocal de Weedoo. Comment puis-je vous aider ?",
            is_public=True,
            is_active=True,
            model_name="gemini-2.5-flash-native-audio-preview-09-2025"
        )
        
        db.add(french_agent)
        db.commit()
        db.refresh(french_agent)
        
        print(f"✅ French demo agent created!")
        print(f"   Name: {french_agent.name}")
        print(f"   ID: {french_agent.id}")
        print(f"   Language: {french_agent.language}")
        
        # Create English demo agent
        print("\n📝 Creating English demo agent...")
        
        english_agent = VoiceAgent(
            user_id=user.id,
            name="English Demo Assistant",
            description="English demonstration agent to test the platform",
            language="en-US",
            voice_id="en-US-Neural2-D",
            system_prompt="""You are an intelligent and helpful voice assistant of Weedoo who always responds in English in a natural and friendly manner.

You can help with:
- Answering general questions
- Having natural conversations
- Providing information
- Being courteous and professional

Always stay polite, clear and concise in your responses.""",
            greeting="Hello, I'm a voice agent from Weedoo. How can I help you?",
            is_public=True,
            is_active=True,
            model_name="gemini-2.5-flash-native-audio-preview-09-2025"
        )
        
        db.add(english_agent)
        db.commit()
        db.refresh(english_agent)
        
        print(f"✅ English demo agent created!")
        print(f"   Name: {english_agent.name}")
        print(f"   ID: {english_agent.id}")
        print(f"   Language: {english_agent.language}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Initializing demo agents...\n")
    success = init_demo_agent()
    
    if success:
        print("\n✅ Demo agents are ready!")
        print("   🇫🇷 French: Assistant Démo Français")
        print("   🇬🇧 English: English Demo Assistant")
        print("\nYou can now visit: http://localhost:3000/demo")
    else:
        print("\n❌ Failed to initialize demo agents")
        print("Check the error messages above")

