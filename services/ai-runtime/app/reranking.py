"""Optional cross-encoder reranking for an already tenant-filtered candidate set."""

from __future__ import annotations

import math
from typing import Any, Protocol


class PairScorer(Protocol):
    def predict(self, pairs: list[tuple[str, str]]) -> Any: ...


def rerank_candidates(
    query: str,
    candidates: list[dict[str, Any]],
    scorer: PairScorer,
) -> list[dict[str, Any]]:
    """Score query/document pairs and sort descending, preserving stable ties.

    The function does not retrieve candidates or change tenant scope. Callers must
    pass only candidates returned by the tenant-filtered retrieval query.
    """
    if not candidates:
        return []

    pairs = [
        (query, f"{item.get('title', '')}\n{item.get('content', '')}")
        for item in candidates
    ]
    raw_scores = scorer.predict(pairs)
    scores = [float(score) for score in raw_scores]
    if len(scores) != len(candidates) or not all(math.isfinite(score) for score in scores):
        raise ValueError("Reranker returned invalid or non-finite scores")

    ranked = []
    for position, (item, score) in enumerate(zip(candidates, scores)):
        ranked.append(({**item, "rerankScore": score}, position))
    ranked.sort(key=lambda row: (-row[0]["rerankScore"], row[1]))
    return [item for item, _ in ranked]
