"""
Test script to verify agent responses work correctly.
This directly tests the FrenchVoiceAgentService similar to how the backend uses it.
"""

import asyncio
import sys
import os
import io
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from app.models import VoiceAgent, Call, CallStatus
from app.services.agent_service import FrenchVoiceAgentService
from app.models.database import SessionLocal

print("=" * 70)
print("AGENT RESPONSE TEST - Debugging No-Response Issue")
print("=" * 70)

async def test_agent_response():
    """Test if the agent can start a session and receive responses"""
    
    db = SessionLocal()
    
    try:
        # 1. Check for existing agent
        print("\n✓ STEP 1: Checking for test agent...")
        print("-" * 70)
        
        agent = db.query(VoiceAgent).filter(VoiceAgent.is_public == True).first()
        
        if not agent:
            print("❌ No public agent found. Creating a test agent...")
            # Create a simple test agent
            agent = VoiceAgent(
                name="Test Agent",
                user_id=1,
                language="en-US",
                system_prompt="You are a helpful and friendly assistant. Respond concisely and naturally.",
                is_public=True,
                is_active=True,
                model_name="gemini-2.5-flash-native-audio-preview-09-2025"
            )
            db.add(agent)
            db.commit()
            db.refresh(agent)
            print(f"✓ Created test agent: {agent.name} (ID: {agent.id})")
        else:
            print(f"✓ Found agent: {agent.name} (ID: {agent.id})")
            print(f"  - Model: {agent.model_name}")
            print(f"  - System Prompt: {agent.system_prompt[:60]}...")
            print(f"  - RAG Enabled: {agent.rag_enabled}")
        
        # 2. Create a call record
        print("\n✓ STEP 2: Creating call record...")
        print("-" * 70)
        
        call = Call(
            user_id=agent.user_id,
            agent_id=agent.id,
            session_id="test-session-" + os.urandom(4).hex(),
            status=CallStatus.INITIATED
        )
        db.add(call)
        db.commit()
        db.refresh(call)
        print(f"✓ Created call: {call.session_id}")
        
        # 3. Initialize agent service
        print("\n✓ STEP 3: Initializing FrenchVoiceAgentService...")
        print("-" * 70)
        
        try:
            agent_service = FrenchVoiceAgentService(agent, call)
            print(f"✓ Service initialized")
            print(f"  - Config response_modalities: {agent_service.config.get('response_modalities')}")
            print(f"  - Config enable_input_transcription: {agent_service.config.get('enable_input_transcription')}")
            print(f"  - System instruction set: {'system_instruction' in agent_service.config}")
        except Exception as e:
            print(f"❌ Failed to initialize service: {e}")
            return False
        
        # 4. Start session
        print("\n✓ STEP 4: Starting Gemini session...")
        print("-" * 70)
        
        try:
            success = await agent_service.start_session()
            if not success:
                print(f"❌ Failed to start session")
                return False
            print(f"✓ Session started successfully")
        except Exception as e:
            print(f"❌ Exception during session start: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # 5. Send test audio and listen for response
        print("\n✓ STEP 5: Sending test audio and listening for response...")
        print("-" * 70)
        
        try:
            # Create dummy audio (silence for 0.5 seconds at 16000 Hz, 16-bit PCM)
            sample_rate = 16000
            duration = 0.5
            samples = int(duration * sample_rate)
            dummy_audio = b'\x00\x00' * samples
            
            print(f"   Sending {len(dummy_audio)} bytes of silent audio...")
            
            # Send audio
            await agent_service.send_audio(dummy_audio)
            
            # Try to receive responses
            print(f"   Listening for responses (10 seconds timeout)...")
            response_count = 0
            receive_timeout = 10.0
            start_time = asyncio.get_event_loop().time()
            
            # Create receive task
            receive_task = asyncio.create_task(agent_service.receive_audio().__anext__())
            send_task = asyncio.create_task(agent_service.send_realtime_input())
            
            try:
                while asyncio.get_event_loop().time() - start_time < receive_timeout:
                    try:
                        # Wait for response with short timeout
                        response = await asyncio.wait_for(receive_task, timeout=1.0)
                        response_count += 1
                        print(f"   ✓ Received response #{response_count}: {len(response)} bytes of audio")
                        # Get next response
                        receive_task = asyncio.create_task(agent_service.receive_audio().__anext__())
                    except asyncio.TimeoutError:
                        # No response yet, continue waiting
                        elapsed = asyncio.get_event_loop().time() - start_time
                        print(f"   ... Waiting ({elapsed:.1f}s elapsed)...")
                        await asyncio.sleep(0.5)
                    except StopAsyncIteration:
                        break
            except Exception as e:
                print(f"   Exception while listening: {e}")
            finally:
                send_task.cancel()
                receive_task.cancel()
                try:
                    await send_task
                except asyncio.CancelledError:
                    pass
                try:
                    await receive_task
                except (asyncio.CancelledError, StopAsyncIteration):
                    pass
            
            if response_count > 0:
                print(f"\n✓ Received {response_count} responses from agent!")
            else:
                print(f"\n⚠️  No audio responses received")
                print(f"   This could mean:")
                print(f"   1. Agent is processing but hasn't sent audio yet")
                print(f"   2. Response modalities issue")
                print(f"   3. API connection issue")
        
        except Exception as e:
            print(f"❌ Exception during audio test: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Clean up
            await agent_service.end_session()
            print(f"\n✓ Session ended")
        
        print("\n" + "=" * 70)
        print("✅ AGENT RESPONSE TEST COMPLETE")
        print("=" * 70)
        print("\nSummary:")
        print(f"  - Agent: {agent.name}")
        print(f"  - Model: {agent.model_name}")
        print(f"  - Session: {call.session_id}")
        print(f"  - Responses received: {response_count}")
        print(f"  - Config includes TEXT: {'TEXT' in agent_service.config.get('response_modalities', [])}")
        print(f"  - Input transcription enabled: {agent_service.config.get('enable_input_transcription')}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("Starting agent response test...\n")
    try:
        success = asyncio.run(test_agent_response())
        if success:
            print("\n✅ All tests passed!")
        else:
            print("\n❌ Test failed!")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
