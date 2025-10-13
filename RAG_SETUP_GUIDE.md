# RAG (Knowledge Base) Setup Guide

## 📚 Overview

Your voice agents can now have a **knowledge base** powered by RAG (Retrieval-Augmented Generation). This allows agents to answer questions based on:
- 📄 **PDF documents** (including scanned PDFs with OCR)
- 🌐 **Website content** (automatically scraped)

## ✅ What's Been Added

### Backend Components
- ✅ **Document Models** (`backend/app/models/document.py`)
  - `Document`: Stores knowledge sources (PDFs, websites)
  - `DocumentChunk`: Text chunks with vector embeddings for semantic search

- ✅ **Services**
  - `DocumentService`: PDF upload, text extraction, OCR for scanned PDFs
  - `RAGService`: Embedding generation, semantic search
  - `WebScraperService`: Website content extraction

- ✅ **API Endpoints** (`backend/app/api/documents.py`)
  - `POST /api/v1/agents/{id}/documents` - Upload PDF
  - `POST /api/v1/agents/{id}/documents/website` - Scrape website
  - `GET /api/v1/agents/{id}/documents` - List documents
  - `DELETE /api/v1/agents/{id}/documents/{doc_id}` - Delete document
  - `PUT /api/v1/agents/{id}/rag/toggle` - Enable/disable RAG

### Frontend Components
- ✅ **Agent Form Page** (`frontend/src/pages/AgentFormPage.tsx`)
  - Added "Enable Knowledge Base (RAG)" checkbox
  - PDF upload area (drag & drop)
  - Website URL input
  - Document list with status indicators
  - Available when editing an existing agent

## 🚀 Installation Steps

### 1. Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

**New dependencies:**
- `pymupdf` - Fast PDF processing
- `sentence-transformers` - Embedding generation
- `beautifulsoup4`, `html2text` - Web scraping
- `openai` - OCR for scanned PDFs (optional)
- `numpy` - Vector operations

### 2. Set Up Environment Variables

Add to your `.env` file:

```env
# Required for scanned PDF OCR (optional)
OPENAI_API_KEY=sk-your-openai-api-key-here
```

**Note:** OCR is only needed if you want to process scanned PDFs. Standard text-based PDFs work without it.

### 3. Create Database Tables

#### For Supabase (Production):

Run the SQL migration in Supabase SQL Editor:

```bash
# Open database/add_rag_tables.sql and run it in Supabase
```

This will:
- Add `rag_enabled` and `rag_config` columns to `voice_agents`
- Create `documents` table
- Create `document_chunks` table
- Add indexes for performance

#### For SQLite (Development):

Tables will be created automatically on first run.

### 4. Restart Backend Server

```bash
cd backend
python -m app.main
# or
uvicorn app.main:app --reload
```

## 🎯 How to Use

### 1. Create or Edit an Agent

1. Go to **Dashboard → Agents**
2. Create a new agent or edit an existing one
3. Check **"Enable Knowledge Base (RAG)"**
4. Save the agent

### 2. Add Knowledge Sources

Once RAG is enabled, you'll see the **Knowledge Base** section:

#### Upload a PDF:
- Click **"Choose PDF"**
- Select a PDF file (max 10MB)
- Supports both regular and scanned PDFs (with OCR)
- Processing happens automatically

#### Add a Website:
- Enter website URL (e.g., `https://docs.example.com`)
- Click **"Add"**
- Content is scraped and processed automatically

### 3. View Documents

The document list shows:
- 📄 PDF or 🌐 Website icon
- Status: Processing → Completed
- Number of chunks created
- Delete option

### 4. Use in Conversations

When RAG is enabled, the agent will:
1. Automatically search relevant documents for each user query
2. Include context from top 5 matching chunks
3. Provide answers based on your knowledge base

## 🔧 Technical Details

### PDF Processing
- Uses **PyMuPDF** (fast and reliable)
- Automatic scanned PDF detection
- OpenAI Vision API for OCR (GPT-4o)
- Text extraction and chunking

### Embeddings
- Model: `all-MiniLM-L6-v2` (384 dimensions)
- Fast, efficient, good quality
- Embeddings stored in database as JSON

### Chunking
- Chunk size: 500 words
- Overlap: 50 words (for context continuity)
- Metadata preserved (page numbers, source info)

### Semantic Search
- Cosine similarity
- Retrieves top 5 most relevant chunks
- Minimum similarity threshold: 0.3

## 📊 Architecture

```
User Query
    ↓
Generate Query Embedding
    ↓
Search Document Chunks (Cosine Similarity)
    ↓
Retrieve Top 5 Relevant Chunks
    ↓
Format Context for LLM
    ↓
Agent Response with Context
```

## ⚙️ Configuration

### Adjust Chunk Size

In `document_service.py` and `web_scraper_service.py`:

```python
def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50):
```

### Change Number of Retrieved Chunks

In `rag_service.py`:

```python
async def search_similar_chunks(
    self,
    db: Session,
    agent_id: int,
    query: str,
    top_k: int = 5,  # Change this
    min_similarity: float = 0.3
):
```

### Change Embedding Model

In `rag_service.py`:

```python
def __init__(self):
    self.embedding_model_name = "all-MiniLM-L6-v2"  # Change this
```

Popular alternatives:
- `all-mpnet-base-v2` (768 dims, higher quality, slower)
- `paraphrase-multilingual-MiniLM-L12-v2` (384 dims, multilingual)

## 🐛 Troubleshooting

### "No text could be extracted from PDF"
- **Cause**: Scanned PDF without OpenAI API key
- **Solution**: Add `OPENAI_API_KEY` to `.env`

### "OpenAI OCR failed"
- **Cause**: Invalid API key or rate limit
- **Solution**: Check API key, check OpenAI quota

### "Import error: cannot import fitz"
- **Cause**: PyMuPDF not installed
- **Solution**: `pip install pymupdf==1.23.26`

### "Module 'sentence_transformers' not found"
- **Cause**: Dependencies not installed
- **Solution**: `pip install sentence-transformers==2.7.0`

### Documents not showing up
- **Cause**: Database tables not created
- **Solution**: Run `database/add_rag_tables.sql` in Supabase

## 🎨 Customization

### Add More Source Types

You can extend to support:
- Plain text files
- Word documents (.docx)
- CSV/Excel files
- Google Docs
- Notion pages

Just add new methods to `document_service.py` or create new service classes.

### Integrate Vector Database

For production at scale, consider:
- **Pinecone** (managed vector DB)
- **Weaviate** (open-source)
- **Qdrant** (Rust-based, fast)
- **Chroma** (local, simple)

Replace the in-database JSON embeddings with proper vector store.

## 📚 Resources

- [PyMuPDF Documentation](https://pymupdf.readthedocs.io/)
- [Sentence Transformers](https://www.sbert.net/)
- [OpenAI Vision API](https://platform.openai.com/docs/guides/vision)
- [RAG Best Practices](https://www.pinecone.io/learn/retrieval-augmented-generation/)

## 🎉 You're Ready!

Your voice agents now have a powerful knowledge base system. Upload documents, add websites, and let your agents provide intelligent, context-aware responses!
