from app.rag.knowledge import KnowledgeService


class RagService(KnowledgeService):
    """Semantic name used by the Agent architecture; retrieval stays reusable."""


__all__ = ["RagService"]
