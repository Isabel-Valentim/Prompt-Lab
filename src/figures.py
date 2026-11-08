"""Builds the README images from results/*_test.json.

Usage:
    python src/figures.py     # writes docs/cover_en.png, docs/cover_pt.png and docs/cost_vs_quality.png
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

INK, MUTED, ACCENT, BAD, BG = "#1f2937", "#6b7280", "#2563eb", "#dc2626", "#ffffff"

TEXT = {
    "en": {
        "kicker": "PROMPT ENGINEERING EXPERIMENT",
        "title": "Which prompt tips actually help?",
        "sub": "5 prompt versions · 301 real consumer complaints · gpt-4o-mini",
        "issue": "Issue F1",
        "product": "Product accuracy",
        "span": "v1 → v5",
        "note": "Few-shot: no gain, 2x the cost",
        "foot": "github.com/Isabel-Valentim/Prompt-Lab",
    },
    "pt": {
        "kicker": "EXPERIMENTO DE ENGENHARIA DE PROMPT",
        "title": "Quais dicas de prompt ajudam de verdade?",
        "sub": "5 versões de prompt · 301 reclamações reais · gpt-4o-mini",
        "issue": "F1 do problema",
        "product": "Acurácia do produto",
        "span": "v1 → v5",
        "note": "Few-shot: sem ganho, 2x o custo",
        "foot": "github.com/Isabel-Valentim/Prompt-Lab",
    },
}


def load() -> list[dict]:
    files = sorted((ROOT / "results").glob("v*_test.json"), key=lambda p: int(p.name.split("_")[0][1:]))
    return [json.loads(p.read_text(encoding="utf-8"))["summary"] for p in files]


def fmt(x: float, lang: str, pct: bool = False) -> str:
    s = f"{x:.0%}" if pct else f"{x:.2f}"
    return s.replace(".", ",") if lang == "pt" else s


def cover(rows: list[dict], lang: str) -> Path:
    t = TEXT[lang]
    first, last = rows[0], rows[-1]
    fig = plt.figure(figsize=(12, 6.27), dpi=100, facecolor=BG)

    fig.text(0.06, 0.86, t["kicker"], fontsize=13, color=ACCENT, weight="bold")
    fig.text(0.06, 0.74, t["title"], fontsize=29, color=INK, weight="bold")
    fig.text(0.06, 0.66, t["sub"], fontsize=15, color=MUTED)

    metrics = [
        (t["issue"], fmt(first["issue"]["macro_f1"], lang), fmt(last["issue"]["macro_f1"], lang)),
        (t["product"], fmt(first["product"]["accuracy"], lang, True), fmt(last["product"]["accuracy"], lang, True)),
    ]
    renderer = fig.canvas.get_renderer()

    def right_edge(txt) -> float:
        return txt.get_window_extent(renderer).x1 / fig.bbox.width

    for i, (label, before, after) in enumerate(metrics):
        x = 0.06 + i * 0.30
        fig.text(x, 0.47, f"{label} ({t['span']})", fontsize=15, color=MUTED)
        b = fig.text(x, 0.32, before, fontsize=40, color=MUTED)
        arrow = fig.text(right_edge(b) + 0.012, 0.335, "→", fontsize=30, color=MUTED)
        fig.text(right_edge(arrow) + 0.012, 0.32, after, fontsize=40, color=ACCENT, weight="bold")

    ax = fig.add_axes([0.68, 0.22, 0.27, 0.36])
    versions = [s["version"] for s in rows]
    ys = [s["issue"]["macro_f1"] for s in rows]
    ax.plot(versions, ys, color=ACCENT, linewidth=3, marker="o", markersize=7)
    ax.set_ylim(0, 0.7)
    ax.set_yticks([])
    ax.tick_params(colors=MUTED, labelsize=11, length=0)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#d1d5db")
    ax.set_title(t["issue"], fontsize=12, color=MUTED, loc="left")

    fig.text(0.06, 0.10, t["note"], fontsize=14, color=BAD)
    fig.text(0.95, 0.05, t["foot"], fontsize=11, color=MUTED, ha="right")

    out = DOCS / f"cover_{lang}.png"
    fig.savefig(out, facecolor=BG)
    plt.close(fig)
    return out


def cost_vs_quality(rows: list[dict]) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    for s in rows:
        x = s["avg_input_tokens"] + s["avg_output_tokens"]
        y = s["issue"]["macro_f1"]
        color = ACCENT if s["version"] == rows[-1]["version"] else (BAD if s["version"] == "v3" else MUTED)
        ax.scatter(x, y, s=110, color=color, zorder=3)
        ax.annotate(f"{s['version']}  {s['title']}", (x, y), textcoords="offset points",
                    xytext=(10, -4), fontsize=9, color=INK)
    ax.set_xlabel("Tokens per complaint (cost)", color=INK)
    ax.set_ylabel("Issue macro F1 (quality)", color=INK)
    ax.set_xlim(0, max(s["avg_input_tokens"] + s["avg_output_tokens"] for s in rows) * 1.55)
    ax.set_ylim(0.2, 0.65)
    ax.set_title("Few-shot (v3) cost the most without being the best", loc="left", color=INK, fontsize=12, weight="bold")
    ax.grid(alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    out = DOCS / "cost_vs_quality.png"
    fig.savefig(out)
    plt.close(fig)
    return out


def main() -> None:
    rows = load()
    for path in (cover(rows, "en"), cover(rows, "pt"), cost_vs_quality(rows)):
        print(f"saved {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
