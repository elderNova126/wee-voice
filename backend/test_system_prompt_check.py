"""
Script to verify that system prompts are properly loaded and applied
Usage: python test_system_prompt_check.py <agent_id>
"""

import sys
from app.models.database import SessionLocal
from app.models.agent import VoiceAgent
from app.services.agent_service import FrenchVoiceAgentService
from app.models.call import Call

def test_system_prompt(agent_id: int):
    """Test if system prompt is properly loaded"""
    print(f"\n{'='*60}")
    print(f"SYSTEM PROMPT VERIFICATION FOR AGENT {agent_id}")
    print(f"{'='*60}\n")
    
    db = SessionLocal()
    
    try:
        # Get agent
        agent = db.query(VoiceAgent).filter(VoiceAgent.id == agent_id).first()
        
        if not agent:
            print(f"❌ Agent {agent_id} not found!")
            return False
        
        print(f"Agent Name: {agent.name}")
        print(f"Language: {agent.language}")
        print(f"RAG Enabled: {agent.rag_enabled}")
        print(f"\n{'='*60}")
        print("STORED SYSTEM PROMPT:")
        print(f"{'='*60}")
        print(agent.system_prompt)
        print(f"\n{'='*60}")
        
        # Create a mock call to test service initialization
        mock_call = Call(
            user_id=agent.user_id,
            agent_id=agent.id,
            session_id="test-session"
        )
        
        # Initialize service to see what config it builds
        print("\nInitializing agent service...")
        service = FrenchVoiceAgentService(agent, mock_call)
        config = service._build_config()
        
        print(f"\n{'='*60}")
        print("FINAL SYSTEM INSTRUCTION SENT TO GEMINI:")
        print(f"{'='*60}")
        
        # Extract the system instruction from config
        if "system_instruction" in config:
            instruction_parts = config["system_instruction"].parts
            for part in instruction_parts:
                if hasattr(part, 'text'):
                    print(part.text)
        
        print(f"\n{'='*60}")
        print("ANALYSIS:")
        print(f"{'='*60}")
        
        # Check if the user's prompt is present
        user_prompt_start = agent.system_prompt[:50]
        instruction_text = instruction_parts[0].text if instruction_parts else ""
        
        if user_prompt_start in instruction_text:
            print("✅ User's custom system prompt is included")
            
            # Check if it's at the beginning
            if instruction_text.startswith(agent.system_prompt):
                print("✅ User's prompt is at the BEGINNING (highest priority)")
            else:
                print("⚠️  User's prompt is NOT at the beginning")
        else:
            print("❌ User's custom system prompt is NOT found!")
            return False
        
        # Check for conflicting identity statements
        conflicting_phrases = [
            "you are an assistant",
            "you are a voice assistant", 
            "assistant by google",
            "i am an assistant",
            "i am gemini",
            "my name is gemini"
        ]
        
        instruction_lower = instruction_text.lower()
        found_conflicts = [p for p in conflicting_phrases if p in instruction_lower and p not in agent.system_prompt.lower()]
        
        if found_conflicts:
            print(f"⚠️  WARNING: Found potentially conflicting identity statements:")
            for phrase in found_conflicts:
                print(f"     - '{phrase}'")
            print("     These might override your custom identity!")
        else:
            print("✅ No conflicting identity statements found")
        
        # Check for identity enforcement
        if "you are not gemini" in instruction_lower or "not an ai assistant" in instruction_lower:
            print("✅ Identity enforcement instructions present")
        else:
            print("⚠️  Warning: No explicit identity enforcement found")
        
        print(f"\n{'='*60}")
        print("RECOMMENDATIONS:")
        print(f"{'='*60}")
        
        if agent.system_prompt.strip().startswith("You are"):
            print("✅ Your prompt clearly defines identity")
        else:
            print("💡 Consider starting your prompt with 'You are...' for clarity")
        
        if "respond" in agent.system_prompt.lower() or "answer" in agent.system_prompt.lower():
            print("✅ Your prompt includes response guidance")
        else:
            print("💡 Consider adding how the agent should respond to questions")
        
        print("\n✅ System prompt check complete!\n")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_system_prompt_check.py <agent_id>")
        print("\nExample:")
        print("  python test_system_prompt_check.py 2")
        sys.exit(1)
    
    agent_id = int(sys.argv[1])
    test_system_prompt(agent_id)

