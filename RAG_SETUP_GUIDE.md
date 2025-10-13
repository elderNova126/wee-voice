# RAG (Retrieval-Augmented Generation) Setup Guide

## Overview

Your VoiceAgent platform now supports **RAG with PDF documents**! This allows your voice agents to answer questions based on uploaded PDF documents during real-time conversations.

## 🎯 Features

- ✅ **PDF Upload & Processing**: Upload PDFs up to 10MB
- ✅ **Scanned PDF Support**: Automatic OCR using OpenAI Vision API (GPT-4o)
- ✅ **Website Scraping**: Extract content from any web page
- ✅ **Automatic Chunking**: Documents are intelligently split into searchable chunks
- ✅ **Semantic Search**: Uses sentence transformers for accurate document retrieval
- ✅ **Vector Storage**: ChromaDB for persistent vector embeddings
- ✅ **Real-time Integration**: Documents are searched during voice conversations
- ✅ **Multi-language Support**: Works with French and English agents
- ✅ **Document Management UI**: Upload, view, and delete documents per agent

## 📦 Installation

### 1. Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

This will install:
- `pymupdf` - Fast PDF processing and text extraction
- `Pillow` - Image processing
- `openai` - OCR via OpenAI Vision API for scanned PDFs
- `beautifulsoup4`, `requests`, `html2text` - Web scraping
- `chromadb`, `langchain-chroma` - Vector database
- `sentence-transformers` - Embeddings generation

**No additional system dependencies required!** PyMuPDF is self-contained.

### 2. Run Database Migration

Apply the database schema for documents:

```bash
# Using PostgreSQL/Supabase
psql -U your_user -d your_database -f database/add_rag_tables.sql

# Or connect to your Supabase project and run the SQL file
```

The migration adds:
- `documents` table - Stores PDF metadata
- `document_chunks` table - Stores text chunks with embeddings
- `rag_enabled` and `rag_config` columns to `voice_agents` table

### 3. Configure Environment Variables

Add your OpenAI API key to `.env` file:

```bash
# .env
OPENAI_API_KEY=sk-your-openai-api-key-here
GOOGLE_API_KEY=your-gemini-api-key
```

The OpenAI key is used exclusively for OCR on scanned PDFs.

### 4. Create Upload Directory

```bash
mkdir -p backend/uploads/documents
mkdir -p backend/data/chroma
```

## 🚀 Usage

### Step 1: Enable RAG for an Agent

1. Navigate to **Agents** page
2. Click the **Documents icon** (purple) on any agent card
3. Toggle **RAG Enabled** to ON

### Step 2: Add Knowledge Sources

**Option A: Upload PDF Documents**
1. On the Documents page, click **Choose File**
2. Select a PDF (max 10MB, supports scanned PDFs)
3. Wait for processing (automatic chunking and embedding generation)
4. Document status will show as **Completed** when ready

**Option B: Scrape Websites**
1. Enter a URL in the website scraping field
2. Click **Scrape**
3. The page content will be extracted and processed
4. Works with any public website (documentation, articles, etc.)

### Step 3: Test in Voice Conversation

1. Start a voice conversation with the agent
2. Ask questions related to the uploaded documents
3. The agent will automatically search and use relevant information

## 🔧 How It Works

### Architecture

```
User Voice Input
    ↓
Gemini 2.5 Flash (Audio Native)
    ↓
[RAG Document Search Tool - if RAG enabled]
    ↓
Retrieve Top 3 Relevant Chunks
    ↓
Inject Context into Response
    ↓
Agent Response (Audio)
```

### RAG Pipeline

1. **Document Upload**: PDF is saved and queued for processing
2. **Text Extraction**: 
   - Regular PDFs: `PyMuPDF` extracts text (fast and reliable)
   - Scanned PDFs: Auto-detected and processed with OpenAI Vision OCR
3. **Chunking**: Text is split into ~1000 character chunks with 200 char overlap
4. **Embedding**: `all-MiniLM-L6-v2` model generates embeddings
5. **Storage**: Embeddings stored in ChromaDB + PostgreSQL backup
6. **Retrieval**: During conversation, semantic search finds relevant chunks
7. **Response**: Agent uses retrieved context to answer accurately

### OCR for Scanned PDFs

The system **automatically detects** scanned PDFs by analyzing:
- Text density (less than 200 characters per page)
- Presence of images on pages
- PyMuPDF renders each page as high-quality image
- OpenAI GPT-4o Vision API extracts text from each page
- Extracted text is processed like regular PDFs

**Cost**: ~$0.01-0.02 per scanned page (OpenAI pricing)

**Benefits of PyMuPDF**:
- 5-10x faster than other PDF libraries
- Better text extraction quality
- Built-in image rendering (no external dependencies)
- Handles complex PDF formats reliably

### Website Scraping

The system can scrape and process web pages:
- Extracts text content from HTML
- Removes navigation, scripts, and styling
- Converts to clean markdown format
- Preserves structure and formatting
- Automatically chunks like PDF documents

**Supported**: Any public website (documentation, articles, blogs, etc.)  
**Best for**: Product docs, FAQs, knowledge bases, tutorials

### Embedding Model

- **Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Dimensions**: 384
- **Language**: Multi-lingual (supports French & English)
- **Speed**: ~3000 sentences/second on CPU
- **Size**: ~80MB

## 📝 API Endpoints

### Upload PDF Document
```http
POST /api/v1/agents/{agent_id}/documents
Content-Type: multipart/form-data

file: <PDF file>
```

### Scrape Website
```http
POST /api/v1/agents/{agent_id}/documents/website
Content-Type: application/json

{
  "url": "https://example.com/documentation"
}
```

### List Documents
```http
GET /api/v1/agents/{agent_id}/documents
```

### Delete Document
```http
DELETE /api/v1/agents/{agent_id}/documents/{document_id}
```

### Toggle RAG
```http
PUT /api/v1/agents/{agent_id}/rag/toggle
Content-Type: multipart/form-data

enabled: true/false
```

## ⚙️ Configuration

### Chunk Settings

Modify in `backend/app/services/document_service.py`:

```python
self.chunk_size = 1000      # characters per chunk
self.chunk_overlap = 200    # overlap between chunks
```

### Retrieval Settings

Modify in `backend/app/services/rag_service.py`:

```python
top_k=3,                    # number of chunks to retrieve
score_threshold=0.3         # minimum similarity score (0-1)
```

### Vector Database

ChromaDB data is stored in:
```
backend/data/chroma/
```

To reset vector database:
```bash
rm -rf backend/data/chroma
```

## 🧪 Testing

### 1. Test Document Upload

```python
# backend/test_rag.py
import asyncio
from app.services.document_service import DocumentProcessingService
from app.services.rag_service import get_rag_service

async def test_upload():
    service = DocumentProcessingService()
    
    with open('test.pdf', 'rb') as f:
        content = f.read()
    
    doc = await service.upload_and_process_document(
        file_content=content,
        filename='test.pdf',
        agent_id=1,
        user_id=1
    )
    
    # Generate embeddings
    rag_service = get_rag_service()
    await rag_service.embed_document_chunks(doc.id)
    
    print(f"Document uploaded: {doc.id}")

asyncio.run(test_upload())
```

### 2. Test Retrieval

```python
async def test_retrieval():
    rag_service = get_rag_service()
    
    results = await rag_service.retrieve_relevant_chunks(
        query="What is the main topic?",
        agent_id=1,
        top_k=3
    )
    
    for chunk in results:
        print(f"Similarity: {chunk['similarity']:.2f}")
        print(f"Content: {chunk['content'][:200]}...")
        print()

asyncio.run(test_retrieval())
```

## 🎨 Frontend Components

### AgentDocumentsPage

Location: `frontend/src/pages/AgentDocumentsPage.tsx`

Features:
- Document upload with drag & drop
- Document list with status badges
- RAG toggle switch
- Delete documents
- Real-time processing status

### Integration

The Documents button is added to each agent card with a purple icon.

## 🔍 Troubleshooting

### Issue: Embeddings not generated

**Solution**: Check that ChromaDB directory has write permissions:
```bash
chmod -R 755 backend/data/chroma
```

### Issue: Scanned PDF processing fails

**Solution**: Check that you have:
1. OpenAI API key configured in `.env`
2. PyMuPDF installed correctly
3. Sufficient OpenAI credits

```bash
# Test dependencies
python -c "import fitz; print('PyMuPDF OK')"
python -c "from openai import OpenAI; print('OpenAI OK')"
```

### Issue: Out of memory with large PDFs

**Solution**: Reduce chunk size or process chunks in batches:
```python
self.chunk_size = 500  # Reduce from 1000
```

### Issue: Vector search is slow

**Solution**: Use GPU acceleration (if available):
```python
# In rag_service.py
self.embedding_model = SentenceTransformer(
    self.embedding_model_name,
    device='cuda'  # or 'mps' for Mac
)
```

## 📊 Performance

### Benchmarks (Average)

| Operation | Time | Notes |
|-----------|------|-------|
| PDF Upload (1MB) | 1-2s | File I/O |
| Text Extraction | 2-5s | 10-page PDF |
| Chunking | <1s | Text processing |
| Embedding Generation | 3-10s | 50 chunks on CPU |
| Vector Search | <100ms | Per query |
| Total Processing | 5-20s | End-to-end |

### Optimization Tips

1. **Use GPU**: 5-10x faster embedding generation
2. **Batch Processing**: Process multiple PDFs in parallel
3. **Cache Embeddings**: Store in database for backup
4. **Index Tuning**: Adjust ChromaDB HNSW parameters

## 🔐 Security

### File Validation

- Only PDF files accepted
- Max file size: 10MB
- MIME type validation
- User ownership verification

### Access Control

- Documents are scoped to agents
- Only agent owner can upload/delete
- RAG queries only access agent's documents

## 🚀 Production Deployment

### 1. Environment Variables

```bash
# .env
GOOGLE_API_KEY=your_gemini_api_key
DATABASE_URL=postgresql://user:pass@host:5432/db
```

### 2. Volume Mounts (Docker)

```yaml
volumes:
  - ./uploads:/app/uploads
  - ./data/chroma:/app/data/chroma
```

### 3. Resource Requirements

- **CPU**: 2+ cores recommended
- **RAM**: 4GB minimum (8GB recommended)
- **Storage**: 1GB + (documents + embeddings)
- **GPU**: Optional but recommended for production

## 📚 Examples

### Example Use Cases

1. **Customer Support**: 
   - PDFs: Product manuals, user guides
   - Websites: Online FAQs, support pages, troubleshooting guides
   
2. **HR Assistant**: 
   - PDFs: Company policies, employee handbook
   - Websites: Benefits pages, internal wiki

3. **Sales Agent**: 
   - PDFs: Product catalogs, pricing sheets
   - Websites: Product pages, case studies, comparisons

4. **Legal Assistant**: 
   - PDFs: Contracts, legal documents
   - Websites: Legal blogs, regulations, case law summaries

5. **Education**: 
   - PDFs: Course materials, textbooks
   - Websites: Tutorials, documentation, research articles

### Example Prompts

After uploading documents:

- "What are the main features of this product?"
- "Can you summarize the return policy?"
- "What does section 3.2 say about..."
- "Find information about pricing..."

## 🤝 Contributing

To extend RAG functionality:

1. **Add OCR Support**: For image-based PDFs
2. **Add More File Types**: DOCX, TXT, Markdown
3. **Improve Chunking**: Semantic chunking algorithms
4. **Add Reranking**: Use cross-encoder for better results
5. **Multi-modal**: Support images within documents

## 📄 License

This RAG implementation uses:
- ChromaDB: Apache 2.0
- Sentence Transformers: Apache 2.0
- PyPDF2: BSD License

---

**Need help?** Open an issue or contact support!

