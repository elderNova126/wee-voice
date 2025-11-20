from app.models.database import SessionLocal
from app.models.call import Call, CallMessage

db = SessionLocal()

# Get latest call
call = db.query(Call).order_by(Call.id.desc()).first()

if call:
    messages = db.query(CallMessage).filter(CallMessage.call_id == call.id).all()
    
    print(f"Latest Call ID: {call.id}")
    print(f"Status: {call.status}")
    print(f"Transcript exists: {bool(call.transcript)}")
    print(f"Transcript length: {len(call.transcript) if call.transcript else 0} chars")
    print(f"Messages count: {len(messages)}")
    print(f"Action tags: {call.action_tags}")
    
    if call.transcript:
        print(f"\nTranscript preview:")
        print(call.transcript[:500])
    
    if messages:
        print(f"\nMessages:")
        for msg in messages[:5]:  # Show first 5 messages
            print(f"  [{msg.role}]: {msg.content[:100]}")
else:
    print("No calls found in database")

db.close()

