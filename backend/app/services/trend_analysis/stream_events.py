"""One completion envelope for fresh and cached multi-period narratives."""
from typing import Any


def analysis_completion(
    dataset: dict[str, Any], *, analysis_id: int | None, narrative: str,
    citations: list[dict], grounded: int, unverified: int, mismatched: int,
    cached: bool, invalidated: bool, usage: dict,
) -> dict[str, Any]:
    return {
        "type": "complete", "kind": "analysis", "analysis_id": analysis_id,
        "snapshot_id": dataset.get("snapshot_id"), "narrative": narrative,
        "citations": citations, "grounded": grounded, "unverified": unverified,
        "mismatched": mismatched, "cached": cached, "invalidated": invalidated,
        "n_periods": len(dataset["periods"]), "usage": usage,
    }
