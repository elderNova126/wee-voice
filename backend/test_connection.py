#!/usr/bin/env python3
"""
Test script to verify Gemini API connection
"""
import os
import asyncio
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

async def test_gemini_connection():
    """Test Gemini Live API connection"""
    api_key = os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        print("❌ GOOGLE_API_KEY not set in .env file")
        return False
    
    print(f"✅ API Key found: {api_key[:20]}...")
    
    try:
        client = genai.Client(api_key=api_key)
        print("✅ Gemini client created successfully")
        
        # Test configuration
        config = {
            "response_modalities": ["AUDIO"],
            "system_instruction": types.Content(
                parts=[types.Part(text="You are a helpful assistant. Respond in French.")]
            ),
        }
        
        print("\n🔌 Attempting to connect to Gemini Live API...")
        print(f"   Model: gemini-2.5-flash-preview-native-audio-dialog")
        
        async with client.aio.live.connect(
            model="gemini-2.5-flash-preview-native-audio-dialog",
            config=config
        ) as session:
            print("✅ Successfully connected to Gemini Live API!")
            
            # Send a simple text message
            print("\n📤 Sending test message...")
            await session.send(input="Bonjour", end_of_turn=True)
            
            # Wait for response
            print("⏳ Waiting for response...")
            turn = session.receive()
            async for response in turn:
                if response.text:
                    print(f"✅ Received response: {response.text}")
                    return True
            
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 Testing Gemini API Connection\n")
    print("="*60)
    success = asyncio.run(test_gemini_connection())
    print("="*60)
    
    if success:
        print("\n✅ All tests passed! Your Gemini API is working correctly.")
    else:
        print("\n❌ Tests failed. Please check your GOOGLE_API_KEY and try again.")

