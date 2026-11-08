"""Runs a prompt version over a split and writes the metrics to results/.

Usage:
    python src/run_eval.py --prompt v1 --split dev
    python src/run_eval.py --prompt v3 --split test --judge
    python src/run_eval.py --prompt all --split test --judge
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import llm  # noqa: E402
from metrics import classification_metrics, confusion, normalize_label, parse_output  # noqa: E402
from prompts import list_versions, load_prompt, load_split, load_taxonomy, render, response_schema  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"


def classify(record: dict, prompt, taxonomy: dict) -> dict:
    messages = render(prompt, record["text"], taxonomy)
    fmt = response_schema(taxonomy) if prompt.structured_output else None
    resp = llm.chat(messages, response_format=fmt)
    parsed = parse_output(resp.content)
    return {
        "id": record["id"],
        "gold_product": record["product"],
        "gold_issue": record["issue"],
        "valid_json": parsed is not None,
        "pred_product": normalize_label(parsed.get("product"), taxonomy["products"]) if parsed else None,
        "pred_issue": normalize_label(parsed.get("issue"), taxonomy["issues"]) if parsed else None,
        "resumo_pt": (parsed or {}).get("resumo_pt"),
        "raw": None if parsed else resp.content[:500],
        "input_tokens": resp.input_tokens,
        "output_tokens": resp.output_tokens,
        "latency_s": resp.latency_s,
    }


def evaluate(version: str, split: str, limit: int | None, judge: bool, workers: int) -> dict:
    prompt = load_prompt(version)
    taxonomy = load_taxonomy()
    records = load_split(split)[:limit] if limit else load_split(split)

    if split == "test":
        leaked = set(prompt.few_shot_ids) & {r["id"] for r in records}
        if leaked:
            raise ValueError(f"Few-shot examples leaking into test: {leaked}")
    # On dev, cases used as prompt examples are not scored (that would be cheating).
    records = [r for r in records if r["id"] not in set(prompt.few_shot_ids)]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(lambda r: classify(r, prompt, taxonomy), records))

    n = len(rows)
    tok_in = sum(r["input_tokens"] for r in rows)
    tok_out = sum(r["output_tokens"] for r in rows)
    summary = {
        "version": version,
        "title": prompt.title,
        "split": split,
        "model": llm.model_name(),
        "n": n,
        "valid_json_rate": round(sum(r["valid_json"] for r in rows) / n, 4),
        "product": classification_metrics(
            [r["gold_product"] for r in rows], [r["pred_product"] for r in rows], taxonomy["products"]
        ),
        "issue": classification_metrics(
            [r["gold_issue"] for r in rows], [r["pred_issue"] for r in rows], taxonomy["issues"]
        ),
        "avg_input_tokens": round(tok_in / n, 1),
        "avg_output_tokens": round(tok_out / n, 1),
        "avg_latency_s": round(sum(r["latency_s"] for r in rows) / n, 3),
        "cost_usd_total": llm.cost_usd(tok_in, tok_out),
    }

    if judge:
        from judge import judge_summaries

        records_by_id = {r["id"]: r for r in records}
        summary["summary_judge"] = judge_summaries(rows, records_by_id, workers)

    out = {
        "summary": summary,
        "confusion_product": confusion(
            [r["gold_product"] for r in rows], [r["pred_product"] for r in rows], taxonomy["products"]
        ),
        "predictions": rows,
    }
    RESULTS.mkdir(exist_ok=True)
    suffix = f"_n{limit}" if limit else ""
    path = RESULTS / f"{version}_{split}{suffix}.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True, help="v1, v2, ... or 'all'")
    ap.add_argument("--split", choices=["dev", "test"], default="dev")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--judge", action="store_true", help="score resumo_pt (Portuguese summary) with an LLM judge")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    versions = list_versions() if args.prompt == "all" else [args.prompt]
    for v in versions:
        s = evaluate(v, args.split, args.limit, args.judge, args.workers)
        judge_txt = f" | summary {s['summary_judge']['mean_score']:.2f}/5" if "summary_judge" in s else ""
        print(
            f"{v} [{args.split}, n={s['n']}] product acc={s['product']['accuracy']:.3f} "
            f"F1={s['product']['macro_f1']:.3f} | issue acc={s['issue']['accuracy']:.3f} "
            f"F1={s['issue']['macro_f1']:.3f} | valid JSON={s['valid_json_rate']:.0%}"
            f" | tokens/case={s['avg_input_tokens'] + s['avg_output_tokens']:.0f}{judge_txt}"
        )


if __name__ == "__main__":
    main()
