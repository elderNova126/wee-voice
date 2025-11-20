"""
Test script for RAG system
Run this to verify RAG functionality is working correctly
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.document_service import DocumentProcessingService
from app.services.rag_service import get_rag_service
from app.models.database import SessionLocal
from app.models import VoiceAgent, User


async def test_rag_system():
    """Test the RAG system end-to-end"""
    
    print("=" * 60)
    print("RAG System Test")
    print("=" * 60)
    
    # Initialize services
    document_service = DocumentProcessingService()
    rag_service = get_rag_service()
    db = SessionLocal()
    
    try:
        # 1. Check if we have a test agent
        print("\n1. Checking for test agent...")
        agent = db.query(VoiceAgent).first()
        
        if not agent:
            print("❌ No agents found. Please create an agent first.")
            return False
        
        print(f"✅ Found agent: {agent.name} (ID: {agent.id})")
        
        # 2. Check document processing service
        print("\n2. Testing document processing service...")
        test_text = "This is a test document for RAG. It contains information about artificial intelligence and machine learning."
        
        # Create a simple test document
        print("   Creating test chunks...")
        chunks = document_service._chunk_text(test_text)
        print(f"✅ Created {len(chunks)} chunks")
        
        # 3. Test embedding generation
        print("\n3. Testing embedding generation...")
        try:
            test_embedding = rag_service.generate_embedding("test query")
            print(f"✅ Generated embedding with {len(test_embedding)} dimensions")
        except Exception as e:
            print(f"❌ Embedding generation failed: {e}")
            return False
        
        # 4. Test ChromaDB connection
        print("\n4. Testing ChromaDB connection...")
        try:
            collection_count = rag_service.collection.count()
            print(f"✅ ChromaDB connected. Collection has {collection_count} documents")
        except Exception as e:
            print(f"❌ ChromaDB connection failed: {e}")
            return False
        
        # 5. Test vector search (if documents exist)
        print("\n5. Testing vector search...")
        if collection_count > 0:
            results = await rag_service.retrieve_relevant_chunks(
                query="test query",
                agent_id=agent.id,
                top_k=3
            )
            print(f"✅ Retrieved {len(results)} relevant chunks")
            
            if results:
                print(f"   Top result similarity: {results[0]['similarity']:.3f}")
        else:
            print("⚠️  No documents in database. Upload a document to test search.")
        
        # 6. Check upload directory
        print("\n6. Checking upload directory...")
        upload_dir = Path("uploads/documents")
        if upload_dir.exists():
            doc_count = len(list(upload_dir.glob("*")))
            print(f"✅ Upload directory exists with {doc_count} files")
        else:
            print("⚠️  Upload directory doesn't exist. Creating it...")
            upload_dir.mkdir(parents=True, exist_ok=True)
            print("✅ Created upload directory")
        
        # 7. Check ChromaDB data directory
        print("\n7. Checking ChromaDB data directory...")
        chroma_dir = Path("data/chroma")
        if chroma_dir.exists():
            print(f"✅ ChromaDB directory exists")
        else:
            print("⚠️  ChromaDB directory doesn't exist. Creating it...")
            chroma_dir.mkdir(parents=True, exist_ok=True)
            print("✅ Created ChromaDB directory")
        
        print("\n" + "=" * 60)
        print("✅ RAG System Test Complete!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Upload a PDF document through the web interface")
        print("2. Enable RAG for your agent")
        print("3. Start a voice conversation and ask questions about the document")
        print("\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    print("Starting RAG system test...\n")
    success = asyncio.run(test_rag_system())
    sys.exit(0 if success else 1)

