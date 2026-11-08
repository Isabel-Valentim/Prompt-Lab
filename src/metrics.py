"""Model output parsing and evaluation metrics."""

from __future__ import annotations

import json
import re

from sklearn.metrics import accuracy_score, confusion_matrix, f1_score


def parse_output(content: str) -> dict | None:
    """Extracts the JSON from a response. Accepts raw JSON, ```json fences, or surrounding text."""
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        brace = re.search(r"\{.*\}", text, re.S)
        if not brace:
            return None
        try:
            obj = json.loads(brace.group(0))
        except json.JSONDecodeError:
            return None
    return obj if isinstance(obj, dict) else None


def normalize_label(value, allowed: list[str]) -> str | None:
    """Maps the model label onto the taxonomy, ignoring case and whitespace. None if off-taxonomy."""
    if not isinstance(value, str):
        return None
    key = re.sub(r"\s+", " ", value).strip().lower()
    for label in allowed:
        if label.lower() == key:
            return label
    return None


def classification_metrics(gold: list[str], pred: list[str | None], labels: list[str]) -> dict:
    """An invalid prediction (None) counts as an error: it becomes a label that never matches."""
    pred_filled = [p if p is not None else "__invalid__" for p in pred]
    return {
        "accuracy": round(accuracy_score(gold, pred_filled), 4),
        "macro_f1": round(f1_score(gold, pred_filled, labels=labels, average="macro", zero_division=0), 4),
        "off_taxonomy_rate": round(sum(p is None for p in pred) / len(pred), 4) if pred else 0.0,
    }


def confusion(gold: list[str], pred: list[str | None], labels: list[str]) -> dict:
    pred_filled = [p if p is not None else "__invalid__" for p in pred]
    cols = labels + ["__invalid__"]
    m = confusion_matrix(gold, pred_filled, labels=cols)
    return {"labels": cols, "matrix": m[: len(labels)].tolist()}
