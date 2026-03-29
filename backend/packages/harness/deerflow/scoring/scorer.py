"""Cross-validation scoring engine for research results.

Scores each subagent result on 4 dimensions:
- Accuracy (30%): Facts backed by sources, named entities, specific data
- Completeness (30%): Covers the question thoroughly
- Source Quality (15%): Has URLs, named sources, diverse domains
- Clarity (25%): Well-structured, readable, no fluff

Tuned for local models (9B–14B) that produce shorter, less citation-heavy
results compared to large cloud models. The weights favour content quality
and structure over raw citation counts.

Each result is also cross-validated against the others — claims that
appear in multiple results get a reliability boost.
"""

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Scoring weights (must sum to 1.0)
# Tuned for local models: less weight on source_quality (small models rarely
# produce markdown citations), more weight on completeness and clarity.
WEIGHT_ACCURACY = 0.30
WEIGHT_COMPLETENESS = 0.30
WEIGHT_SOURCE_QUALITY = 0.15
WEIGHT_CLARITY = 0.25


@dataclass
class ResearchScore:
    """Score for a single research result."""

    agent_index: int  # 0-based
    accuracy: float = 0.0
    completeness: float = 0.0
    source_quality: float = 0.0
    clarity: float = 0.0
    cross_validation_bonus: float = 0.0  # Bonus for claims found in other results
    weighted_total: float = 0.0
    details: dict = field(default_factory=dict)

    def compute_total(self):
        base = (
            self.accuracy * WEIGHT_ACCURACY
            + self.completeness * WEIGHT_COMPLETENESS
            + self.source_quality * WEIGHT_SOURCE_QUALITY
            + self.clarity * WEIGHT_CLARITY
        )
        self.weighted_total = min(base + self.cross_validation_bonus, 100.0)

    def to_dict(self) -> dict:
        return {
            "agent_index": self.agent_index,
            "accuracy": round(self.accuracy, 1),
            "completeness": round(self.completeness, 1),
            "source_quality": round(self.source_quality, 1),
            "clarity": round(self.clarity, 1),
            "cross_validation_bonus": round(self.cross_validation_bonus, 1),
            "weighted_total": round(self.weighted_total, 1),
            "details": self.details,
        }


def _extract_urls(text: str) -> list[str]:
    """Extract URLs from text."""
    return re.findall(r'https?://[^\s\)\]>"\']+', text)


def _extract_citations(text: str) -> list[str]:
    """Extract markdown-style citations [text](url)."""
    return re.findall(r'\[([^\]]+)\]\(https?://[^\)]+\)', text)


def _extract_numbers(text: str) -> list[str]:
    """Extract specific numbers/stats from text."""
    return re.findall(r'\b\d[\d,\.]*(?:\s*(?:%|percent|million|billion|trillion|MB|GB|TB|ms|seconds|users|downloads))\b', text, re.IGNORECASE)


def _extract_named_entities(text: str) -> set[str]:
    """Extract capitalized phrases that look like proper nouns / names."""
    # Match 1-3 Title-Case words in sequence (names, companies, products)
    matches = re.findall(r'\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b', text)
    entities = {m.strip() for m in matches if len(m) > 2}
    # Also match all-caps acronyms (AI, USA, GPT, API, LLM, etc.)
    acronyms = re.findall(r'\b[A-Z]{2,6}\b', text)
    entities.update(acronyms)
    return entities


def _count_paragraphs(text: str) -> int:
    """Count non-empty paragraphs."""
    return len([p for p in text.split('\n\n') if p.strip()])


def _count_headings(text: str) -> int:
    """Count markdown headings."""
    return len(re.findall(r'^#{1,3}\s+', text, re.MULTILINE))


def _count_bullet_points(text: str) -> int:
    """Count bullet points."""
    return len(re.findall(r'^\s*[-*•]\s+', text, re.MULTILINE))


def _score_accuracy(text: str) -> tuple[float, dict]:
    """Score accuracy: specific facts, numbers, named sources."""
    urls = _extract_urls(text)
    citations = _extract_citations(text)
    numbers = _extract_numbers(text)
    entities = _extract_named_entities(text)

    details = {
        "urls": len(urls),
        "citations": len(citations),
        "numbers": len(numbers),
        "entities": len(entities),
    }

    # Score: named entities and specific data matter most for local models
    # (they rarely produce markdown citations, so don't over-weight those)
    score = 0.0
    score += min(len(citations) * 10, 20)  # Up to 20 for citations
    score += min(len(urls) * 8, 20)        # Up to 20 for URLs
    score += min(len(numbers) * 6, 25)     # Up to 25 for specific numbers
    score += min(len(entities) * 3, 35)    # Up to 35 for named entities (strongest signal)

    return min(score, 100.0), details


def _score_completeness(text: str, query: str) -> tuple[float, dict]:
    """Score completeness: length, coverage of query terms."""
    words = text.split()
    word_count = len(words)
    paragraphs = _count_paragraphs(text)

    # Check query term coverage
    query_terms = set(re.findall(r'\b\w{3,}\b', query.lower()))
    text_lower = text.lower()
    covered_terms = sum(1 for t in query_terms if t in text_lower)
    term_coverage = (covered_terms / max(len(query_terms), 1)) * 100

    details = {
        "word_count": word_count,
        "paragraphs": paragraphs,
        "query_term_coverage": round(term_coverage, 1),
    }

    score = 0.0
    # Length scoring: tuned for local 9B models that write 50-200 words
    if word_count < 30:
        score += 10
    elif word_count < 75:
        score += 30
    elif word_count < 150:
        score += 45
    elif word_count < 300:
        score += 55
    else:
        score += 60

    # Query coverage — strong signal, worth up to 40
    score += term_coverage * 0.4

    return min(score, 100.0), details


def _score_source_quality(text: str) -> tuple[float, dict]:
    """Score source quality: URLs, citation format, source diversity."""
    urls = _extract_urls(text)
    citations = _extract_citations(text)

    # Check for diverse domains
    domains = set()
    for url in urls:
        parts = url.split('//')
        if len(parts) > 1:
            domain = parts[1].split('/')[0].split('?')[0]
            domains.add(domain)

    details = {
        "url_count": len(urls),
        "citation_count": len(citations),
        "unique_domains": len(domains),
    }

    score = 0.0
    score += min(len(citations) * 12, 35)  # Up to 35 for proper citations
    score += min(len(urls) * 10, 35)       # Up to 35 for URLs
    score += min(len(domains) * 10, 30)    # Up to 30 for source diversity

    # Base points: if the result mentions ANY source-like content, give credit
    # Local models often reference sources by name without proper URL formatting
    if len(urls) > 0 or len(citations) > 0:
        score = max(score, 25)  # Floor of 25 if any sources present

    return min(score, 100.0), details


def _score_clarity(text: str) -> tuple[float, dict]:
    """Score clarity: structure, formatting, readability."""
    headings = _count_headings(text)
    bullets = _count_bullet_points(text)
    paragraphs = _count_paragraphs(text)
    words = len(text.split())

    # Average sentence length (lower is clearer for research)
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    avg_sentence_len = (sum(len(s.split()) for s in sentences) / max(len(sentences), 1))

    details = {
        "headings": headings,
        "bullet_points": bullets,
        "paragraphs": paragraphs,
        "avg_sentence_length": round(avg_sentence_len, 1),
    }

    score = 0.0
    # Structure — generous: even minimal formatting should score well
    score += min(headings * 12, 25)   # Up to 25 for headings
    score += min(bullets * 4, 25)     # Up to 25 for bullet points
    score += min(paragraphs * 8, 20)  # Up to 20 for paragraphs

    # Readability: prefer 8-25 word sentences (wider range for local models)
    if 8 <= avg_sentence_len <= 25:
        score += 30
    elif avg_sentence_len < 8:
        score += 20
    else:
        score += 10

    return min(score, 100.0), details


def _cross_validate(results: list[str]) -> list[float]:
    """Cross-validate: boost results whose claims appear in others.

    Returns a bonus score (0-10) for each result.
    """
    if len(results) < 2:
        return [0.0] * len(results)

    # Extract named entities from each result
    entity_sets = [_extract_named_entities(r) for r in results]

    bonuses = []
    for i, entities in enumerate(entity_sets):
        if not entities:
            bonuses.append(0.0)
            continue

        # Count how many of this result's entities appear in other results
        confirmed = 0
        for entity in entities:
            others_with_entity = sum(
                1 for j, other_entities in enumerate(entity_sets)
                if j != i and entity in other_entities
            )
            if others_with_entity > 0:
                confirmed += 1

        # Bonus: up to 15 points for cross-validated claims
        ratio = confirmed / max(len(entities), 1)
        bonuses.append(min(ratio * 20, 15.0))

    return bonuses


class CrossValidator:
    """Scores and cross-validates research results from multiple agents."""

    def score_results(self, results: list[str], query: str) -> list[ResearchScore]:
        """Score all results and return sorted scores.

        Args:
            results: List of result texts from each subagent.
            query: The original user query.

        Returns:
            List of ResearchScore objects, sorted by weighted_total descending.
        """
        if not results:
            return []

        scores = []
        for i, text in enumerate(results):
            if not text or len(text.strip()) < 10:
                # Empty or trivial result
                score = ResearchScore(agent_index=i)
                score.details = {"error": "Empty or trivial result"}
                scores.append(score)
                continue

            acc, acc_details = _score_accuracy(text)
            comp, comp_details = _score_completeness(text, query)
            src, src_details = _score_source_quality(text)
            clar, clar_details = _score_clarity(text)

            score = ResearchScore(
                agent_index=i,
                accuracy=acc,
                completeness=comp,
                source_quality=src,
                clarity=clar,
                details={
                    "accuracy": acc_details,
                    "completeness": comp_details,
                    "source_quality": src_details,
                    "clarity": clar_details,
                },
            )
            scores.append(score)

        # Cross-validation bonus
        bonuses = _cross_validate(results)
        for score, bonus in zip(scores, bonuses):
            score.cross_validation_bonus = bonus

        # Compute totals
        for score in scores:
            score.compute_total()

        # Sort by total (best first)
        scores.sort(key=lambda s: s.weighted_total, reverse=True)

        logger.info(
            "Cross-validation scores: %s",
            [(s.agent_index, round(s.weighted_total, 1)) for s in scores],
        )

        return scores
