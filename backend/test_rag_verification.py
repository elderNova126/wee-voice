"""
Test script to verify RAG system is working correctly
Run this after uploading a PDF to verify:
1. Documents are properly stored
2. Embeddings are generated
3. Search works correctly
"""

import asyncio
import sys
from sqlalchemy.orm import Session
from app.models.database import SessionLocal
from app.models.document import Document, DocumentChunk
from app.models.agent import VoiceAgent
from app.services.rag_service import get_rag_service

def test_document_storage(db: Session, agent_id: int):
    """Test if documents are properly stored"""
    print(f"\n{'='*60}")
    print("TEST 1: Document Storage")
    print(f"{'='*60}")
    
    documents = db.query(Document).filter(
        Document.agent_id == agent_id
    ).all()
    
    if not documents:
        print("❌ No documents found for this agent!")
        return False
    
    print(f"✅ Found {len(documents)} document(s)")
    for doc in documents:
        print(f"\n  Document ID: {doc.id}")
        print(f"  Filename: {doc.original_filename}")
        print(f"  Status: {doc.status}")
        print(f"  Total Pages: {doc.total_pages}")
        print(f"  Total Chunks: {doc.total_chunks}")
        print(f"  Processed At: {doc.processed_at}")
    
    return True

def test_embeddings(db: Session, agent_id: int):
    """Test if embeddings are generated"""
    print(f"\n{'='*60}")
    print("TEST 2: Embeddings Generation")
    print(f"{'='*60}")
    
    # Get all chunks for this agent
    chunks = db.query(DocumentChunk).join(Document).filter(
        Document.agent_id == agent_id
    ).all()
    
    if not chunks:
        print("❌ No chunks found!")
        return False
    
    print(f"✅ Found {len(chunks)} chunk(s)")
    
    # Check how many have embeddings
    with_embeddings = sum(1 for chunk in chunks if chunk.embedding)
    without_embeddings = len(chunks) - with_embeddings
    
    print(f"  Chunks with embeddings: {with_embeddings}")
    print(f"  Chunks without embeddings: {without_embeddings}")
    
    if without_embeddings > 0:
        print(f"⚠️  Warning: {without_embeddings} chunks are missing embeddings!")
        return False
    
    # Show sample chunk
    if chunks:
        sample = chunks[0]
        print("\n  Sample Chunk:")
        print(f"    Content: {sample.content[:100]}...")
        print(f"    Embedding length: {len(sample.embedding) if sample.embedding else 0}")
    
    return True

async def test_search(db: Session, agent_id: int, query: str):
    """Test if search works correctly"""
    print(f"\n{'='*60}")
    print("TEST 3: RAG Search")
    print(f"{'='*60}")
    print(f"  Query: '{query}'")
    
    rag_service = get_rag_service()
    
    try:
        # First try with very low threshold to see ALL similarities
        print("\n  Testing with min_similarity=0.0 (showing all chunks)...")
        all_results = await rag_service.search_similar_chunks(
            db=db,
            agent_id=agent_id,
            query=query,
            top_k=10,
            min_similarity=0.0
        )
        
        if all_results:
            print(f"  Found {len(all_results)} chunk(s) with ANY similarity:")
            for i, result in enumerate(all_results[:5], 1):  # Show top 5
                print(f"    Chunk {i}: similarity = {result['similarity']:.4f}")
        else:
            print("  ⚠️ No chunks found at all!")
        
        # Now try with normal threshold
        print("\n  Testing with min_similarity=0.2...")
        results = await rag_service.search_similar_chunks(
            db=db,
            agent_id=agent_id,
            query=query,
            top_k=3,
            min_similarity=0.2
        )
        
        if not results:
            print("❌ No results found with similarity >= 0.2")
            if all_results:
                max_sim = max(r['similarity'] for r in all_results)
                print(f"   Highest similarity found: {max_sim:.4f}")
                print("   Suggestion: Try a more specific query or lower the threshold")
            return False
        
        print(f"✅ Found {len(results)} relevant chunk(s)\n")
        
        for i, result in enumerate(results, 1):
            print(f"  Result {i}:")
            print(f"    Similarity: {result['similarity']:.3f}")
            print(f"    Document ID: {result['document_id']}")
            print(f"    Page: {result.get('page_number', 'N/A')}")
            print(f"    Content: {result['content'][:150]}...")
            print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error during search: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_agent_rag_enabled(db: Session, agent_id: int):
    """Test if RAG is enabled for the agent"""
    print(f"\n{'='*60}")
    print("TEST 4: Agent RAG Configuration")
    print(f"{'='*60}")
    
    agent = db.query(VoiceAgent).filter(VoiceAgent.id == agent_id).first()
    
    if not agent:
        print(f"❌ Agent {agent_id} not found!")
        return False
    
    print(f"  Agent Name: {agent.name}")
    print(f"  RAG Enabled: {agent.rag_enabled}")
    
    if not agent.rag_enabled:
        print("\n⚠️  Warning: RAG is NOT enabled for this agent!")
        print("   It should be automatically enabled when documents are uploaded.")
        return False
    
    print("✅ RAG is properly enabled")
    return True

async def main():
    """Main test function"""
    if len(sys.argv) < 2:
        print("Usage: python test_rag_verification.py <agent_id> [search_query]")
        print("\nExample:")
        print("  python test_rag_verification.py 1")
        print("  python test_rag_verification.py 1 'professional experience'")
        print("\nTips for better queries:")
        print("  - Use keywords from your document")
        print("  - Be specific (e.g., 'work experience' vs 'experiences')")
        print("  - Try nouns rather than questions")
        sys.exit(1)
    
    agent_id = int(sys.argv[1])
    search_query = sys.argv[2] if len(sys.argv) > 2 else "information"
    
    print(f"\n{'#'*60}")
    print(f"  RAG SYSTEM VERIFICATION FOR AGENT {agent_id}")
    print(f"{'#'*60}")
    
    db = SessionLocal()
    
    try:
        # Run all tests
        test1 = test_document_storage(db, agent_id)
        test2 = test_embeddings(db, agent_id)
        test3 = await test_search(db, agent_id, search_query)
        test4 = test_agent_rag_enabled(db, agent_id)
        
        # Summary
        print(f"\n{'='*60}")
        print("TEST SUMMARY")
        print(f"{'='*60}")
        
        all_passed = all([test1, test2, test3, test4])
        
        if all_passed:
            print("✅ All tests passed! RAG system is working correctly.")
        else:
            print("❌ Some tests failed. Please check the output above.")
        
        print()
        
    except Exception as e:
        print(f"\n❌ Error running tests: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())

