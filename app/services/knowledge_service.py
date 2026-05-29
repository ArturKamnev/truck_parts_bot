from __future__ import annotations

from pathlib import Path


class KnowledgeService:
    """File-backed knowledge provider; replace this class with RAG later."""

    def __init__(
        self,
        knowledge_path: Path | str = "company_knowledge.md",
        system_prompt_path: Path | str = "app/prompts/company_system_prompt.md",
    ) -> None:
        self._knowledge_path = Path(knowledge_path)
        self._system_prompt_path = Path(system_prompt_path)
        self._knowledge_cache: str | None = None
        self._prompt_cache: str | None = None

    def get_company_knowledge(self) -> str:
        if self._knowledge_cache is None:
            self._knowledge_cache = self._knowledge_path.read_text(encoding="utf-8")
        return self._knowledge_cache

    def get_system_prompt(self) -> str:
        if self._prompt_cache is None:
            self._prompt_cache = self._system_prompt_path.read_text(encoding="utf-8")
        return self._prompt_cache

    def build_system_context(self) -> str:
        return (
            f"{self.get_system_prompt().strip()}\n\n"
            "## Company knowledge\n"
            f"{self.get_company_knowledge().strip()}"
        )
