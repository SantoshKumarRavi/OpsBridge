"""Deterministic onboarding policy checks, kept independent of external services."""

from datetime import date, datetime
from typing import Any


def assess_policy(state: dict[str, Any]) -> dict[str, Any]:
    request = state["request"]
    documents = request.get("extracted_documents", [])
    missing_fields = []
    review_flags = []

    for document in documents:
        fields = document.get("fields", {})
        document_type = document.get("document_type", "identity")
        if document.get("human_review_required") or float(document.get("confidence", 0)) < 0.85:
            review_flags.append({
                "document": document.get("document_type", "unknown"),
                "reason": "Confidence is below review threshold.",
            })

        required_fields = (
            ("document_number", "expiry_date")
            if document_type == "work_eligibility"
            else ("full_name", "document_number")
        )
        for field in required_fields:
            if not fields.get(field):
                missing_fields.append({"document": document.get("document_type", "unknown"), "field": field})

        if fields.get("expiry_date"):
            try:
                raw_expiry = str(fields["expiry_date"])
                expiry_date = (
                    datetime.fromisoformat(raw_expiry.replace("Z", "+00:00")).date()
                    if "T" in raw_expiry
                    else date.fromisoformat(raw_expiry[:10])
                )
                if expiry_date < date.today():
                    review_flags.append({
                        "document": document_type,
                        "reason": "Document appears expired; request human verification.",
                    })
            except (ValueError, TypeError):
                review_flags.append({
                    "document": document_type,
                    "reason": "Expiration date could not be interpreted.",
                })

        extracted_name = " ".join(str(fields.get("full_name", "")).casefold().split())
        profile_name = " ".join(str(request.get("worker_profile", {}).get("name", "")).casefold().split())
        if extracted_name and profile_name and extracted_name != profile_name:
            review_flags.append({
                "document": document_type,
                "reason": "Document name differs from the worker profile.",
            })

    state["assessment"] = {
        "missing_fields": missing_fields,
        "review_flags": review_flags,
        "documents_received": len(documents),
        "policy_text": request.get("policy_text"),
    }
    return state


async def prepare_recommendation(state: dict[str, Any]) -> dict[str, Any]:
    assessment = state["assessment"]
    suggested_next_step = (
        "request_changes"
        if assessment["missing_fields"]
        else "human_review"
        if assessment["review_flags"]
        else "ready_for_human_approval"
    )
    explanation = {
        "summary": "Documents were checked against the supplied onboarding policy.",
        "missing_fields": assessment["missing_fields"],
        "review_flags": assessment["review_flags"],
        "decision": "AI provides an advisory recommendation only. An authorized person must make the final decision.",
    }
    state["recommendation"] = {
        "suggested_next_step": suggested_next_step,
        "explanation": explanation,
        "confidence": 0.0 if assessment["review_flags"] or assessment["missing_fields"] else 0.9,
        "human_decision_required": True,
    }
    return state
