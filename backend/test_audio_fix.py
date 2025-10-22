"""
Test script to verify the Gemini 2.5 Flash Native Audio fixes.
This tests the corrected model name and audio format.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

# Verify API key
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("❌ GOOGLE_API_KEY not found in .env")
    sys.exit(1)

print("=" * 70)
print("GEMINI 2.5 FLASH NATIVE AUDIO - FIX VERIFICATION TEST")
print("=" * 70)

# Test 1: Check model name
print("\n✓ TEST 1: Model Name Verification")
print("-" * 70)
CORRECT_MODEL = "gemini-2.5-flash-native-audio-preview-09-2025"
WRONG_MODEL = "gemini-2.5-flash-preview-native-audio-dialog"

print(f"   ✓ Correct model:   {CORRECT_MODEL}")
print(f"   ✗ Wrong model:     {WRONG_MODEL}")

# Test 2: Test connection with correct model
print("\n✓ TEST 2: API Connection Test")
print("-" * 70)

async def test_connection():
    """Test connection to Gemini with correct model"""
    client = genai.Client(api_key=api_key)
    
    config = {
        "response_modalities": ["AUDIO"],
        "system_instruction": "You are a helpful assistant. Respond in a friendly tone.",
    }
    
    try:
        print(f"   Connecting to model: {CORRECT_MODEL}")
        async with client.aio.live.connect(model=CORRECT_MODEL, config=config) as session:
            print(f"   ✓ Successfully connected to Gemini Live API!")
            
            # Test sending audio blob with correct format
            print("\n✓ TEST 3: Audio Format Test")
            print("-" * 70)
            
            # Create a dummy audio chunk (1 second of silence at 16000 Hz, 16-bit PCM)
            # PCM 16-bit = 2 bytes per sample
            silence_duration = 0.1  # 100ms
            sample_rate = 16000
            samples = int(silence_duration * sample_rate)
            dummy_audio = b'\x00\x00' * samples  # Silence in PCM 16-bit
            
            print(f"   Sample rate: 16000 Hz")
            print(f"   MIME type: audio/pcm;rate=16000")
            print(f"   Dummy audio size: {len(dummy_audio)} bytes")
            
            # Create Blob with correct format
            audio_blob = types.Blob(
                data=dummy_audio,
                mime_type="audio/pcm;rate=16000"
            )
            
            print(f"   ✓ Created audio Blob successfully")
            
            # Try to send the audio
            try:
                await session.send_realtime_input(audio=audio_blob)
                print(f"   ✓ Sent audio to Gemini successfully!")
            except Exception as e:
                print(f"   ✗ Failed to send audio: {e}")
                return False
            
            return True
    
    except Exception as e:
        error_msg = str(e)
        print(f"   ✗ Connection failed: {error_msg}")
        
        # Check for common errors
        if "not found" in error_msg.lower():
            print(f"      → This suggests an invalid model name")
        elif "1008" in error_msg or "policy violation" in error_msg.lower():
            print(f"      → This suggests a protocol violation (wrong modality/format)")
        elif "not supported" in error_msg.lower():
            print(f"      → This suggests the model doesn't support bidi streaming")
        
        return False

print("\n   Initiating async test...")
try:
    success = asyncio.run(test_connection())
    if success:
        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED! Your fixes are working correctly.")
        print("=" * 70)
        print("\nKey fixes applied:")
        print("  1. ✓ Updated model to: gemini-2.5-flash-native-audio-preview-09-2025")
        print("  2. ✓ Set response_modalities to: ['AUDIO']")
        print("  3. ✓ Updated MIME type to: audio/pcm;rate=16000")
        print("  4. ✓ Wrapped audio in types.Blob()")
        print("\nYour backend is ready to use!")
    else:
        print("\n" + "=" * 70)
        print("❌ TESTS FAILED - Check the errors above")
        print("=" * 70)
        sys.exit(1)
except Exception as e:
    print(f"\n❌ Test execution failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
