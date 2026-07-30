"""Small, dependency-free retrieval layer for authored AcmeWorks policies."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .schemas import PolicyCitation

WORD_PATTERN = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]+", re.IGNORECASE)
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "do",
    "does",
    "for",
    "how",
    "i",
    "is",
    "of",
    "policy",
    "the",
    "to",
    "what",
}
CHINESE_ALIASES = {
    "工时": {"time", "reporting"},
    "提交": {"submission", "submit"},
    "截止": {"deadline"},
    "审批": {"approval", "approve"},
    "加班": {"overtime"},
    "协作": {"collaboration"},
    "数据": {"data"},
    "保留": {"retention"},
    "演示": {"demo"},
}


@dataclass(frozen=True)
class PolicyChunk:
    """One independently retrievable Markdown section."""

    source_id: str
    title: str
    section: str
    relative_path: str
    text: str
    tokens: frozenset[str]


@dataclass(frozen=True)
class RetrievalResult:
    """A grounded answer and the policy sections that support it."""

    answer: str
    citations: list[PolicyCitation]
    confidence: float


class PolicyKnowledgeBase:
    """Load Markdown policies and answer only when lexical evidence is strong."""

    def __init__(self, root: Path, *, minimum_score: float = 0.16) -> None:
        self.root = root
        self.minimum_score = minimum_score
        self.chunks = self._load_chunks(root)
        self._document_frequency = Counter(
            token for chunk in self.chunks for token in chunk.tokens
        )

    def search(self, query: str, *, limit: int = 3) -> RetrievalResult | None:
        """Retrieve policy sections and compose an extractive grounded answer."""

        query_tokens = _tokenize(query)
        if not query_tokens or not self.chunks:
            return None

        ranked = sorted(
            (
                (self._score(chunk, query_tokens), chunk)
                for chunk in self.chunks
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        selected = [
            (score, chunk)
            for score, chunk in ranked[:limit]
            if score >= self.minimum_score
        ]
        if not selected:
            return None

        citations = [
            PolicyCitation(
                source_id=chunk.source_id,
                title=chunk.title,
                section=chunk.section,
                path=chunk.relative_path,
                excerpt=_first_sentences(chunk.text, 2),
            )
            for _, chunk in selected
        ]
        answer = " ".join(citation.excerpt for citation in citations)
        return RetrievalResult(
            answer=answer,
            citations=citations,
            confidence=round(selected[0][0], 3),
        )

    def _score(self, chunk: PolicyChunk, query_tokens: set[str]) -> float:
        """Calculate normalized IDF overlap with small title/section boosts."""

        overlap = query_tokens & chunk.tokens
        if not overlap:
            return 0.0
        corpus_size = max(len(self.chunks), 1)
        weighted_overlap = sum(
            math.log(
                (corpus_size + 1)
                / (self._document_frequency[token] + 1)
            )
            + 1
            for token in overlap
        )
        query_weight = sum(
            math.log(
                (corpus_size + 1)
                / (self._document_frequency[token] + 1)
            )
            + 1
            for token in query_tokens
        )
        score = weighted_overlap / max(query_weight, 1)
        heading_tokens = _tokenize(f"{chunk.title} {chunk.section}")
        if overlap & heading_tokens:
            score += 0.12
        return min(score, 1.0)

    @staticmethod
    def _load_chunks(root: Path) -> list[PolicyChunk]:
        if not root.exists():
            return []
        chunks: list[PolicyChunk] = []
        for path in sorted(root.glob("*.md")):
            if path.name.casefold() == "readme.md":
                continue
            metadata, body = _parse_front_matter(path.read_text("utf-8"))
            source_id = metadata.get("id", path.stem)
            title = metadata.get("title", path.stem.replace("-", " ").title())
            for section, text in _split_sections(body):
                chunks.append(
                    PolicyChunk(
                        source_id=source_id,
                        title=title,
                        section=section,
                        relative_path=f"knowledge-base/{path.name}",
                        text=text,
                        tokens=frozenset(
                            _tokenize(f"{title} {section} {text}")
                        ),
                    )
                )
        return chunks


def _tokenize(text: str) -> set[str]:
    """Tokenize English words and add Chinese character bigrams."""

    tokens: set[str] = set()
    for phrase, aliases in CHINESE_ALIASES.items():
        if phrase in text:
            tokens.update(aliases)
    for match in WORD_PATTERN.findall(text.casefold()):
        if re.fullmatch(r"[\u4e00-\u9fff]+", match):
            tokens.update(match)
            tokens.update(
                match[index : index + 2]
                for index in range(max(len(match) - 1, 0))
            )
        else:
            if match not in STOP_WORDS:
                tokens.add(match)
    return tokens


def _parse_front_matter(content: str) -> tuple[dict[str, str], str]:
    if not content.startswith("---\n"):
        return {}, content
    _, metadata_text, body = content.split("---\n", 2)
    metadata = {}
    for line in metadata_text.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            metadata[key.strip()] = value.strip()
    return metadata, body


def _split_sections(body: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_heading = "Overview"
    current_lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("## "):
            if current_lines:
                text = " ".join(item.strip() for item in current_lines if item.strip())
                if text:
                    sections.append((current_heading, text))
            current_heading = line[3:].strip()
            current_lines = []
        elif not line.startswith("# "):
            current_lines.append(line)
    text = " ".join(item.strip() for item in current_lines if item.strip())
    if text:
        sections.append((current_heading, text))
    return sections


def _first_sentences(text: str, count: int) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentences[:count])
