import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from app.config import Settings


INJECTION_PATTERNS = (
    "忽略之前",
    "忽略以上",
    "system prompt",
    "developer message",
    "泄露提示词",
    "执行任意",
    "调用未授权工具",
)


@dataclass(frozen=True)
class KnowledgeChunk:
    document_id: str
    title: str
    section: str
    source: str
    content: str

    @property
    def chunk_id(self) -> str:
        value = f"{self.document_id}:{self.section}:{self.content}"
        return hashlib.sha256(value.encode("utf-8")).hexdigest()


class KnowledgeService:
    def __init__(self, settings: Settings) -> None:
        base = Path(settings.knowledge_dir)
        self._directory = (
            base if base.is_absolute() else settings.env_file_dir / base
        ).resolve()
        self._top_k = settings.rag_top_k
        self._chunks = self._load_chunks()
        self._vector = (
            PgVectorRetriever(settings) if settings.rag_pgvector_enabled else None
        )
        self.vector_error: str | None = None

    async def initialize(self) -> None:
        if self._vector is None:
            return
        try:
            await self._vector.initialize(self._chunks)
        except Exception as exc:
            # Keyword retrieval remains available when PostgreSQL or embeddings fail.
            self.vector_error = str(exc)
            await self._vector.close()
            self._vector = None

    async def close(self) -> None:
        if self._vector is not None:
            await self._vector.close()

    async def search(self, query: str) -> dict[str, Any]:
        if self._looks_like_injection(query):
            return {
                "error": "检测到提示词注入内容，知识检索已拒绝该指令。",
                "citations": [],
            }

        keyword_ranked = self._keyword_search(query, self._top_k * 2)
        vector_ranked = (
            await self._vector.search(query, self._top_k * 2)
            if self._vector is not None
            else []
        )
        scores: dict[str, float] = {}
        chunks: dict[str, KnowledgeChunk] = {}
        for ranked in (keyword_ranked, vector_ranked):
            for rank, chunk in enumerate(ranked, start=1):
                chunks[chunk.chunk_id] = chunk
                scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0) + 1 / (
                    60 + rank
                )
        selected = sorted(
            chunks.values(), key=lambda item: scores[item.chunk_id], reverse=True
        )[: self._top_k]
        return {
            "query": query,
            "evidence": [
                {
                    "title": chunk.title,
                    "section": chunk.section,
                    "content": chunk.content,
                    "source": chunk.source,
                    "citation": f"[{chunk.title} - {chunk.section}]",
                }
                for chunk in selected
            ],
            "citations": [
                {
                    "documentId": chunk.document_id,
                    "title": chunk.title,
                    "section": chunk.section,
                    "source": chunk.source,
                }
                for chunk in selected
            ],
            "retrievalMode": "hybrid" if vector_ranked else "keyword",
        }

    def _keyword_search(self, query: str, limit: int) -> list[KnowledgeChunk]:
        query_terms = self._terms(query)
        scored = []
        for chunk in self._chunks:
            terms = self._terms(f"{chunk.title} {chunk.section} {chunk.content}")
            overlap = len(query_terms & terms)
            if overlap:
                score = overlap / math.sqrt(max(1, len(terms)))
                scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:limit]]

    def _load_chunks(self) -> list[KnowledgeChunk]:
        chunks: list[KnowledgeChunk] = []
        if not self._directory.exists():
            return chunks
        for path in sorted(self._directory.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            title = path.stem
            source = path.name
            section = "概述"
            buffer: list[str] = []
            for line in text.splitlines():
                if line.startswith("# "):
                    title = line[2:].strip()
                elif line.startswith("## "):
                    self._append_chunk(
                        chunks, path.stem, title, section, source, buffer
                    )
                    section = line[3:].strip()
                    buffer = []
                elif not line.startswith("> metadata:"):
                    buffer.append(line)
            self._append_chunk(chunks, path.stem, title, section, source, buffer)
        return [
            chunk
            for chunk in chunks
            if not self._looks_like_injection(chunk.content)
        ]

    @staticmethod
    def _append_chunk(
        chunks: list[KnowledgeChunk],
        document_id: str,
        title: str,
        section: str,
        source: str,
        lines: list[str],
    ) -> None:
        content = "\n".join(lines).strip()
        if content:
            chunks.append(
                KnowledgeChunk(document_id, title, section, source, content)
            )

    @staticmethod
    def _terms(text: str) -> set[str]:
        normalized = re.sub(r"\s+", "", text.lower())
        chinese = re.findall(r"[\u4e00-\u9fff]+", normalized)
        bigrams = {
            word[index : index + 2]
            for word in chinese
            for index in range(max(0, len(word) - 1))
        }
        latin = set(re.findall(r"[a-z0-9]{2,}", normalized))
        return bigrams | latin

    @staticmethod
    def _looks_like_injection(text: str) -> bool:
        lowered = text.lower()
        return any(pattern in lowered for pattern in INJECTION_PATTERNS)


class PgVectorRetriever:
    def __init__(self, settings: Settings) -> None:
        self._dsn = settings.rag_postgres_dsn
        self._dimension = settings.rag_embedding_dimension
        self._model = settings.rag_embedding_model
        self._client = AsyncOpenAI(
            api_key=settings.rag_embedding_api_key or settings.llm_api_key,
            base_url=settings.rag_embedding_base_url or settings.llm_base_url,
        )
        self._pool: Any = None

    async def initialize(self, chunks: list[KnowledgeChunk]) -> None:
        import asyncpg

        self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=4)
        async with self._pool.acquire() as connection:
            await connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS agent_knowledge_chunk (
                    chunk_id VARCHAR(64) PRIMARY KEY,
                    document_id VARCHAR(100) NOT NULL,
                    title VARCHAR(200) NOT NULL,
                    section VARCHAR(200) NOT NULL,
                    source VARCHAR(500) NOT NULL,
                    content TEXT NOT NULL,
                    embedding vector({self._dimension}) NOT NULL
                )
                """
            )
            count = await connection.fetchval(
                "SELECT COUNT(*) FROM agent_knowledge_chunk"
            )
        if count == 0 and chunks:
            await self._index(chunks)

    async def search(self, query: str, limit: int) -> list[KnowledgeChunk]:
        embedding = await self._embed(query)
        vector = self._vector_literal(embedding)
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT document_id, title, section, source, content
                FROM agent_knowledge_chunk
                ORDER BY embedding <=> $1::vector
                LIMIT $2
                """,
                vector,
                limit,
            )
        return [
            KnowledgeChunk(
                row["document_id"],
                row["title"],
                row["section"],
                row["source"],
                row["content"],
            )
            for row in rows
        ]

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def _index(self, chunks: list[KnowledgeChunk]) -> None:
        embeddings = await self._embeddings([chunk.content for chunk in chunks])
        async with self._pool.acquire() as connection:
            await connection.executemany(
                """
                INSERT INTO agent_knowledge_chunk
                    (chunk_id, document_id, title, section, source, content, embedding)
                VALUES ($1, $2, $3, $4, $5, $6, $7::vector)
                ON CONFLICT (chunk_id) DO UPDATE SET
                    content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding
                """,
                [
                    (
                        chunk.chunk_id,
                        chunk.document_id,
                        chunk.title,
                        chunk.section,
                        chunk.source,
                        chunk.content,
                        self._vector_literal(embedding),
                    )
                    for chunk, embedding in zip(chunks, embeddings, strict=True)
                ],
            )

    async def _embed(self, text: str) -> list[float]:
        return (await self._embeddings([text]))[0]

    async def _embeddings(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(
            model=self._model, input=texts
        )
        result = [item.embedding for item in response.data]
        if result and len(result[0]) != self._dimension:
            raise ValueError(
                f"Embedding维度为{len(result[0])}，配置为{self._dimension}"
            )
        return result

    @staticmethod
    def _vector_literal(values: list[float]) -> str:
        return "[" + ",".join(str(value) for value in values) + "]"
