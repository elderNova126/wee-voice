#!/usr/bin/env python3
"""
Standalone AudioSocket server for testing with Asterisk.
This bypasses FastAPI/Gemini to test raw AudioSocket protocol.

Usage:
    python standalone_audiosocket.py [port]
    
Then configure Asterisk extensions.conf:
    AudioSocket(${CALL_UUID},127.0.0.1:9093)
"""
import socket
import struct
import threading
import time
import sys

MSG_UUID = 0x01
MSG_AUDIO = 0x10
MSG_HANGUP = 0x00
MSG_ERROR = 0xFF

FRAME_SIZE = 320
SILENCE_FRAME = b'\x00' * FRAME_SIZE


def handle_client(conn, addr):
    """Handle a single AudioSocket connection"""
    print(f"\n[{addr}] Connected!")
    
    frames_sent = 0
    frames_received = 0
    running = True
    
    def send_silence():
        """Send silence frames continuously"""
        nonlocal frames_sent, running
        while running:
            try:
                header = struct.pack('>BH', MSG_AUDIO, FRAME_SIZE)
                conn.sendall(header + SILENCE_FRAME)
                frames_sent += 1
                if frames_sent == 1:
                    print(f"[{addr}] First silence frame SENT")
                if frames_sent % 100 == 0:
                    print(f"[{addr}] Sent {frames_sent} frames")
                time.sleep(0.02)  # 20ms = 50fps
            except Exception as e:
                print(f"[{addr}] Send error: {e}")
                running = False
                break
    
    # Start sending silence IMMEDIATELY in background thread
    sender = threading.Thread(target=send_silence, daemon=True)
    sender.start()
    print(f"[{addr}] Silence sender started")
    
    # Read packets from client
    try:
        conn.settimeout(30)  # 30 second overall timeout
        
        while running:
            # Read header (3 bytes)
            header = b''
            while len(header) < 3:
                chunk = conn.recv(3 - len(header))
                if not chunk:
                    print(f"[{addr}] Connection closed by client")
                    running = False
                    break
                header += chunk
            
            if not running or len(header) < 3:
                break
            
            msg_type = header[0]
            payload_len = struct.unpack('>H', header[1:3])[0]
            
            # Read payload
            payload = b''
            while len(payload) < payload_len:
                chunk = conn.recv(payload_len - len(payload))
                if not chunk:
                    break
                payload += chunk
            
            if msg_type == MSG_UUID:
                uuid_str = payload.decode('ascii', errors='replace')
                print(f"[{addr}] UUID received: {uuid_str}")
            elif msg_type == MSG_AUDIO:
                frames_received += 1
                if frames_received == 1:
                    print(f"[{addr}] First audio frame RECEIVED (len={len(payload)})")
                if frames_received % 100 == 0:
                    print(f"[{addr}] Received {frames_received} frames")
            elif msg_type == MSG_HANGUP:
                print(f"[{addr}] Hangup received")
                running = False
                break
            elif msg_type == MSG_ERROR:
                print(f"[{addr}] Error received: {payload}")
                running = False
                break
    
    except socket.timeout:
        print(f"[{addr}] Read timeout")
    except Exception as e:
        print(f"[{addr}] Error: {e}")
    finally:
        running = False
        conn.close()
        print(f"[{addr}] Closed. Sent={frames_sent}, Received={frames_received}\n")


def main(port=9093):
    """Run the standalone AudioSocket server"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', port))
    server.listen(5)
    
    print(f"\n{'='*60}")
    print(f"Standalone AudioSocket Server")
    print(f"Listening on 0.0.0.0:{port}")
    print(f"{'='*60}")
    print(f"\nUpdate Asterisk extensions.conf to use port {port}:")
    print(f"  AudioSocket(${{CALL_UUID}},127.0.0.1:{port})")
    print(f"\nWaiting for connections...\n")
    
    while True:
        try:
            conn, addr = server.accept()
            # Handle each connection in a new thread
            thread = threading.Thread(target=handle_client, args=(conn, addr))
            thread.start()
        except KeyboardInterrupt:
            print("\nShutting down...")
            break
    
    server.close()


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9093
    main(port)

