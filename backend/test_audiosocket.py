#!/usr/bin/env python3
"""
Test script to simulate Asterisk AudioSocket connection.
This helps debug the AudioSocket handler without making actual phone calls.

Usage:
    python test_audiosocket.py [host] [port]
    
Example:
    python test_audiosocket.py 127.0.0.1 9092
"""
import socket
import struct
import time
import sys
import uuid

# AudioSocket message types (same as Asterisk)
MSG_UUID = 0x01
MSG_AUDIO = 0x10
MSG_HANGUP = 0x00
MSG_ERROR = 0xFF

# 160 samples at 8kHz = 20ms of audio
FRAME_SIZE = 320  # 160 samples * 2 bytes
SILENCE_FRAME = b'\x00' * FRAME_SIZE


def send_packet(sock, msg_type: int, payload: bytes):
    """Send a packet in AudioSocket format"""
    header = struct.pack('>BH', msg_type, len(payload))
    sock.sendall(header + payload)
    print(f"  SENT: type=0x{msg_type:02x}, len={len(payload)}")


def recv_packet(sock, timeout=5.0):
    """Receive a packet in AudioSocket format"""
    sock.settimeout(timeout)
    try:
        # Read header
        header = sock.recv(3)
        if len(header) < 3:
            print(f"  RECV: incomplete header ({len(header)} bytes)")
            return None, None
        
        msg_type = header[0]
        payload_len = struct.unpack('>H', header[1:3])[0]
        
        # Read payload
        payload = b''
        while len(payload) < payload_len:
            chunk = sock.recv(payload_len - len(payload))
            if not chunk:
                break
            payload += chunk
        
        print(f"  RECV: type=0x{msg_type:02x}, len={len(payload)}")
        return msg_type, payload
    except socket.timeout:
        print("  RECV: timeout")
        return None, None
    except Exception as e:
        print(f"  RECV: error - {e}")
        return None, None


def test_audiosocket(host='127.0.0.1', port=9092):
    """Test the AudioSocket server"""
    print(f"\n{'='*60}")
    print(f"Testing AudioSocket at {host}:{port}")
    print(f"{'='*60}\n")
    
    # Create socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    
    try:
        # Connect
        print(f"[1] Connecting to {host}:{port}...")
        sock.connect((host, port))
        print(f"    ✅ Connected!\n")
        
        # Send UUID (like Asterisk does)
        test_uuid = str(uuid.uuid4())
        print(f"[2] Sending UUID: {test_uuid}")
        send_packet(sock, MSG_UUID, test_uuid.encode('ascii'))
        print(f"    ✅ UUID sent!\n")
        
        # Wait a moment for server to process
        time.sleep(0.5)
        
        # Try to receive audio frames from server
        print(f"[3] Waiting for audio frames from server...")
        frames_received = 0
        start_time = time.time()
        
        while time.time() - start_time < 10:  # Wait up to 10 seconds
            msg_type, payload = recv_packet(sock, timeout=1.0)
            
            if msg_type == MSG_AUDIO:
                frames_received += 1
                if frames_received == 1:
                    print(f"    ✅ First audio frame received! (len={len(payload)})")
                if frames_received % 50 == 0:
                    print(f"    Received {frames_received} frames...")
            elif msg_type == MSG_HANGUP:
                print(f"    Server sent hangup")
                break
            elif msg_type == MSG_ERROR:
                print(f"    Server sent error: {payload}")
                break
            elif msg_type is None:
                # Timeout or error, send some audio to keep connection alive
                if frames_received == 0:
                    print(f"    No frames yet, sending test audio...")
                    send_packet(sock, MSG_AUDIO, SILENCE_FRAME)
        
        print(f"\n    Total frames received: {frames_received}")
        
        if frames_received > 0:
            print(f"    ✅ AudioSocket is WORKING!\n")
        else:
            print(f"    ❌ No audio frames received from server\n")
        
        # Send some audio frames (simulate caller speaking)
        print(f"[4] Sending test audio frames...")
        for i in range(10):
            send_packet(sock, MSG_AUDIO, SILENCE_FRAME)
            time.sleep(0.02)  # 20ms per frame
        print(f"    ✅ Sent 10 test audio frames\n")
        
        # Wait for more responses
        print(f"[5] Waiting for AI response...")
        ai_frames = 0
        start_time = time.time()
        
        while time.time() - start_time < 15:  # Wait up to 15 seconds for AI
            msg_type, payload = recv_packet(sock, timeout=1.0)
            
            if msg_type == MSG_AUDIO:
                ai_frames += 1
                if ai_frames == 1:
                    print(f"    ✅ First AI audio frame! (len={len(payload)})")
                if ai_frames % 50 == 0:
                    print(f"    AI frames: {ai_frames}...")
            elif msg_type is None:
                if ai_frames == 0:
                    # Keep sending audio
                    send_packet(sock, MSG_AUDIO, SILENCE_FRAME)
                else:
                    break
        
        print(f"\n    Total AI frames received: {ai_frames}")
        
        # Send hangup
        print(f"\n[6] Sending hangup...")
        send_packet(sock, MSG_HANGUP, b'')
        print(f"    ✅ Hangup sent\n")
        
    except ConnectionRefusedError:
        print(f"    ❌ Connection refused - is the AudioSocket server running?")
        print(f"    Check: ss -tlnp | grep {port}")
    except socket.timeout:
        print(f"    ❌ Connection timeout")
    except Exception as e:
        print(f"    ❌ Error: {e}")
    finally:
        sock.close()
        print(f"[7] Connection closed\n")


if __name__ == '__main__':
    host = sys.argv[1] if len(sys.argv) > 1 else '127.0.0.1'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 9092
    
    test_audiosocket(host, port)

