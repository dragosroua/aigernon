# Vector Memory

AIGernon's vector memory system provides semantic search and retrieval across all your content using ChromaDB and OpenAI embeddings.

## Overview

Vector memory enhances AIGernon's cognitive capabilities by enabling:

- **Semantic search**: Find content by meaning, not just keywords
- **Long-term recall**: Search across years of memories and notes
- **Content indexing**: Import blog posts, documents, and external content
- **Contextual retrieval**: Surface relevant memories during conversations

## Installation

Vector memory is an optional feature. Install with:

```bash
pip install aigernon[vector]
```

This adds ChromaDB as a dependency. The embedding API (OpenAI) uses your existing LLM provider credentials.

## Configuration

Add vector configuration to `~/.aigernon/config.json`:

```json
{
  "vector": {
    "enabled": true,
    "embedding_model": "text-embedding-3-small",
    "chunk_size": 500,
    "chunk_overlap": 50,
    "similarity_threshold": 0.7,
    "max_results": 10,
    "collections": ["memories", "blog", "diary"]
  }
}
```

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `enabled` | `false` | Enable vector memory |
| `embedding_model` | `text-embedding-3-small` | OpenAI embedding model |
| `chunk_size` | `500` | Words per chunk |
| `chunk_overlap` | `50` | Overlap between chunks |
| `similarity_threshold` | `0.7` | Minimum similarity score |
| `max_results` | `10` | Max results per query |
| `collections` | `["memories", "blog", "diary"]` | Enabled collections |

## Collections

Vector memory organizes content into collections:

| Collection | Purpose |
|------------|---------|
| `memories` | Daily notes, long-term memory |
| `blog` | Blog posts and articles |
| `diary` | Personal diary entries |
| `coaching` | Coaching client data |
| `projects` | Project notes and documentation |

## CLI Commands

### Status

```bash
aigernon vector status
```

Shows vector memory configuration and collection statistics.

### Search

```bash
# Search all collections
aigernon vector search "productivity tips"

# Search specific collection
aigernon vector search "GraphQL setup" --collection blog

# Limit results
aigernon vector search "meeting notes" --limit 3
```

### Clear

```bash
# Clear a specific collection
aigernon vector clear --collection blog --yes

# Clear all collections
aigernon vector clear --yes
```

## Importing Content

### Markdown Files

Import markdown files from a directory:

```bash
# Import all .md files recursively
aigernon import markdown ~/Documents/blog/posts

# Custom pattern
aigernon import markdown ~/blog --pattern "**/*.mdx"

# Exclude patterns
aigernon import markdown ~/blog --exclude "**/drafts/**"

# Import to specific collection
aigernon import markdown ~/notes --collection diary
```

The importer handles:
- YAML frontmatter parsing (title, date, tags, categories)
- Markdown section-aware chunking
- HTML stripping from content

### WordPress (GraphQL)

Import from WordPress sites with WPGraphQL plugin:

```bash
# Import all posts
aigernon import wordpress https://example.com/graphql

# Limit number of posts
aigernon import wordpress https://wp.example.com/graphql --max 100

# Filter by category
aigernon import wordpress https://wp.example.com/graphql --category tech

# Custom batch size
aigernon import wordpress https://wp.example.com/graphql --batch-size 50
```

## How It Works

### Chunking

Documents are split into chunks for effective embedding:

```
┌─────────────────────────────────────────────────────────────┐
│  Original document: 2000 words                              │
├─────────────────────────────────────────────────────────────┤
│  Chunk 1: ~500 words (intro + first section)                │
│  ─────────────────────────────────────────────              │
│  Chunk 2: ~500 words (with 50 word overlap)                 │
│  ─────────────────────────────────────────────              │
│  Chunk 3: ~500 words (with 50 word overlap)                 │
│  ─────────────────────────────────────────────              │
│  Chunk 4: ~500 words (conclusion)                           │
└─────────────────────────────────────────────────────────────┘
```

Markdown-aware chunking preserves section boundaries when possible.

### Embedding

Each chunk is converted to a 1536-dimensional vector using OpenAI's `text-embedding-3-small` model:

```
"productivity tips for developers"
           ↓
    [0.023, -0.041, 0.019, ..., 0.008]  (1536 floats)
```

### Search

Queries are embedded and compared using cosine similarity:

```
Query: "How to be more productive?"
           ↓
    Embed query
           ↓
    Compare to all chunk embeddings
           ↓
    Return top-K most similar
```

## Storage

Vector data is stored in `~/.aigernon/vectordb/`:

```
~/.aigernon/vectordb/
├── chroma.sqlite3      # Metadata database
└── *.parquet           # Vector data files
```

### Storage Estimates

| Content | Documents | Chunks | Storage |
|---------|-----------|--------|---------|
| 1 year of daily notes | 365 | ~500 | ~5 MB |
| 1000 blog posts | 1000 | ~4000 | ~30 MB |
| 5 years of diary | 1800 | ~3000 | ~25 MB |

## Cost Analysis

### Embedding Costs (OpenAI)

| Model | Cost | Typical Usage |
|-------|------|---------------|
| `text-embedding-3-small` | $0.02 / 1M tokens | ~$0.07 for 1000 blog posts |
| `text-embedding-3-large` | $0.13 / 1M tokens | Higher quality, 6x cost |

### Latency

| Operation | Time |
|-----------|------|
| Embed query | 80-150ms |
| Search (local) | 5-20ms |
| Total query | ~100-170ms |

## Programmatic Usage

### Basic Search

```python
from aigernon.memory import VectorStore, EmbeddingProvider

# Create embedding provider
embeddings = EmbeddingProvider(
    model="text-embedding-3-small",
    api_key="your-api-key",
)

# Create vector store
store = VectorStore(
    persist_directory="~/.aigernon/vectordb",
    embedding_provider=embeddings,
)

# Search
results = store.search(
    collection="blog",
    query="productivity tips",
    n_results=5,
)

for result in results:
    print(f"[{result.score:.2f}] {result.metadata.get('title')}")
    print(f"  {result.text[:100]}...")
```

### Adding Documents

```python
from aigernon.memory import VectorStore, TextChunker

chunker = TextChunker(chunk_size=500, overlap=50)
store = VectorStore(persist_directory="~/.aigernon/vectordb")

# Chunk and add
chunks = chunker.chunk_markdown(
    text="# My Post\n\nContent here...",
    metadata={"title": "My Post", "date": "2024-01-01"},
)

store.add(
    collection="blog",
    documents=[c.text for c in chunks],
    metadatas=[c.metadata for c in chunks],
)
```

### Custom Importer

```python
from aigernon.importers import BaseImporter, ImportResult

class MyImporter(BaseImporter):
    def import_all(self, source: str) -> ImportResult:
        result = ImportResult(success=True)

        # Fetch your content
        documents = self.fetch_documents(source)

        for doc in documents:
            chunks = self.chunker.chunk_text(doc.content, doc.metadata)
            self._index_chunks(chunks, base_id=doc.id)
            result.documents_processed += 1
            result.chunks_created += len(chunks)

        return result
```

## Best Practices

### Chunking Strategy

- **Blog posts**: Use `chunk_blog_post()` for rich metadata
- **Markdown**: Use `chunk_markdown()` for section-aware chunking
- **Plain text**: Use `chunk_text()` with appropriate size

### Metadata

Include rich metadata for filtering:

```python
metadata = {
    "source": "blog",
    "title": "Post Title",
    "date": "2024-01-01",
    "categories": ["tech", "python"],
    "tags": ["tutorial", "beginner"],
    "url": "/posts/my-post",
}
```

### Filtering

Use metadata filters for targeted search:

```python
# Search only recent posts
results = store.search(
    collection="blog",
    query="python tips",
    where={"date": {"$gte": "2024-01-01"}},
)

# Search by category
results = store.search(
    collection="blog",
    query="tutorials",
    where={"categories": "tech"},
)
```

## Troubleshooting

### "ChromaDB not installed"

```bash
pip install aigernon[vector]
```

### "No API key configured"

Ensure your LLM provider has an API key configured in `config.json`. Vector memory uses the same credentials for embeddings.

### Slow imports

- Reduce batch size for WordPress imports
- Use `--max` to limit initial import
- Run imports during off-peak hours

### High storage usage

- Clear unused collections: `aigernon vector clear -c old_collection --yes`
- Reduce chunk overlap
- Increase minimum chunk size
