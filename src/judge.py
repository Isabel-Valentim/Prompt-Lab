"""LLM-as-judge: scores the Portuguese summary against the original complaint with a fixed rubric."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import llm
from metrics import parse_output

RUBRIC = """You are a strict quality reviewer for a customer-support team in Brazil.
You will receive a consumer complaint (in English) and a 2-sentence summary written in Portuguese.

Score the summary from 1 to 5:
5 = faithful, complete (who/what/what the consumer wants), natural Portuguese, no invented facts.
4 = faithful with a minor omission or awkward wording.
3 = misses an important point OR is too vague to act on.
2 = contains a factual error or a detail not present in the complaint.
1 = wrong, empty, not in Portuguese, or mostly invented.

Rules:
- "XXXX" in the complaint is redacted data. Inventing names, dates or amounts for it is a factual error.
- Judge only faithfulness and usefulness, not style preferences.

Return JSON: {"hallucination": true|false, "score": <1-5>, "reason": "<one sentence>"}"""

JUDGE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "summary_judgement",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "hallucination": {"type": "boolean"},
                "score": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
                "reason": {"type": "string"},
            },
            "required": ["hallucination", "score", "reason"],
            "additionalProperties": False,
        },
    },
}


def _judge_one(text: str, summary: str | None) -> dict:
    if not summary:
        return {"hallucination": False, "score": 1, "reason": "missing summary"}
    messages = [
        {"role": "system", "content": RUBRIC},
        {"role": "user", "content": f"Complaint:\n{text}\n\nSummary (pt-BR):\n{summary}"},
    ]
    resp = llm.chat(messages, response_format=JUDGE_SCHEMA)
    return parse_output(resp.content) or {"hallucination": False, "score": 1, "reason": "judge returned no JSON"}


def judge_summaries(rows: list[dict], records_by_id: dict, workers: int = 8) -> dict:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        verdicts = list(pool.map(lambda r: _judge_one(records_by_id[r["id"]]["text"], r["resumo_pt"]), rows))
    for row, v in zip(rows, verdicts):
        row["judge"] = v
    n = len(verdicts)
    return {
        "mean_score": round(sum(v["score"] for v in verdicts) / n, 3),
        "hallucination_rate": round(sum(bool(v["hallucination"]) for v in verdicts) / n, 4),
        "score_distribution": {s: sum(v["score"] == s for v in verdicts) for s in range(1, 6)},
    }


if __name__ == "__main__":
    print(json.dumps(JUDGE_SCHEMA, indent=2))
