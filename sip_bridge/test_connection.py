#!/usr/bin/env python3
"""
Test WebSocket Connection to Railway Backend
Tests the connection before deploying full SIP bridge
"""
import asyncio
import websockets
import sys
from config import BACKEND_WS_URL, BACKEND_API_KEY

async def test_connection():
    """Test WebSocket connection to Railway backend"""
    print("🧪 Testing WebSocket Connection")
    print("=" * 50)
    
    # Build WebSocket URL with agent_id=1 (test agent)
    ws_url = f"{BACKEND_WS_URL}/1"
    if BACKEND_API_KEY:
        ws_url += f"?api_key={BACKEND_API_KEY}"
    
    print(f"📡 Connecting to: {ws_url}")
    
    try:
        async with websockets.connect(ws_url, ping_interval=20) as ws:
            print("✅ Connected successfully!")
            
            # Send test audio (silent PCM16)
            test_audio = b'\x00' * 2048  # 2048 bytes of silence
            print(f"📤 Sending test audio: {len(test_audio)} bytes")
            await ws.send(test_audio)
            print("✅ Test audio sent")
            
            # Wait for response
            print("⏳ Waiting for response (5 second timeout)...")
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                print(f"✅ Received response: {len(response)} bytes")
                print(f"   Response type: {type(response)}")
                
                # If text response, show it
                if isinstance(response, str):
                    print(f"   Content: {response[:100]}...")
                
                print("\n🎉 CONNECTION TEST PASSED!")
                print("=" * 50)
                print("Your Railway backend is ready to receive SIP calls!")
                return True
                
            except asyncio.TimeoutError:
                print("⚠️  No response received (timeout)")
                print("   This might be normal if agent needs wake-up time")
                print("\n✅ Connection works but no immediate response")
                print("=" * 50)
                return True
                
    except websockets.exceptions.WebSocketException as e:
        print(f"\n❌ WebSocket Error: {e}")
        print("=" * 50)
        print("\n🔧 Troubleshooting:")
        print("1. Check BACKEND_WS_URL in .env file")
        print("2. Verify Railway app is running: railway status")
        print("3. Check Railway logs: railway logs")
        print("4. Ensure API key is correct")
        print("5. Test Railway health endpoint:")
        print(f"   curl https://your-app.railway.app/health")
        return False
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("=" * 50)
        return False

if __name__ == "__main__":
    print("\n")
    result = asyncio.run(test_connection())
    print("\n")
    sys.exit(0 if result else 1)

