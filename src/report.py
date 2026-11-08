"""Aggregates results/*.json into a markdown table and a chart.

Usage:
    python src/report.py --split test     # prints the table and saves docs/metrics_test.png
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prompts import load_prompt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def load(split: str) -> list[dict]:
    files = sorted(
        (ROOT / "results").glob(f"v*_{split}.json"), key=lambda p: int(p.name.split("_")[0][1:])
    )
    rows = [json.loads(p.read_text(encoding="utf-8"))["summary"] for p in files]
    for s in rows:  # the title always comes from the current prompt file
        s["title"] = load_prompt(s["version"]).title
    return rows


def table(rows: list[dict]) -> str:
    lines = [
        "| Version | Technique | Product (acc) | Product (macro F1) | Issue (acc) | Issue (macro F1) "
        "| Valid JSON | Summary (judge 1-5) | Summary hallucination | Tokens/case |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in rows:
        j = s.get("summary_judge")
        judge_score = f"{j['mean_score']:.2f}" if j else "–"
        judge_halluc = f"{j['hallucination_rate']:.1%}" if j else "–"
        tokens = s["avg_input_tokens"] + s["avg_output_tokens"]
        lines.append(
            f"| {s['version']} | {s['title']} "
            f"| {s['product']['accuracy']:.1%} | {s['product']['macro_f1']:.3f} "
            f"| {s['issue']['accuracy']:.1%} | {s['issue']['macro_f1']:.3f} "
            f"| {s['valid_json_rate']:.0%} | {judge_score} | {judge_halluc} | {tokens:.0f} |"
        )
    return "\n".join(lines)


def chart(rows: list[dict], split: str) -> Path:
    versions = [s["version"] for s in rows]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    series = {
        "Product (macro F1)": [s["product"]["macro_f1"] for s in rows],
        "Issue (macro F1)": [s["issue"]["macro_f1"] for s in rows],
    }
    for (label, ys), marker in zip(series.items(), ["o", "s"]):
        ax.plot(versions, ys, marker=marker, linewidth=2, label=label)
        for x, y in zip(versions, ys):
            ax.annotate(f"{y:.2f}", (x, y), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("score")
    ax.set_title(f"Metrics by prompt version ({split}, n={rows[0]['n']}, {rows[0]['model']})")
    ax.grid(axis="y", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    out = ROOT / "docs" / f"metrics_{split}.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=150)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], default="test")
    args = ap.parse_args()
    rows = load(args.split)
    if not rows:
        raise SystemExit(f"No results in results/ for split {args.split}")
    print(table(rows))
    print(f"\nChart saved to {chart(rows, args.split).relative_to(ROOT)}")


if __name__ == "__main__":
    main()
