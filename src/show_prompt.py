"""Writes out the exact messages each prompt version sent to the model.

The files in prompts/ are templates: {{products}}, {{issues}}, {{examples}} and {{text}}
are filled in at call time. This script fills them in for one real test complaint and
saves the result to prompts/rendered/, so you can read exactly what the model received.

It also checks that the rendered text is byte-for-byte what was sent: the cache key in
.cache/llm/ is a hash of the full request, so a matching cache file proves it.

Usage:
    python src/show_prompt.py                 # all versions, first test complaint
    python src/show_prompt.py --id 6738291    # a specific complaint
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import llm  # noqa: E402
from prompts import list_versions, load_prompt, load_split, load_taxonomy, render, response_schema  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "prompts" / "rendered"


def build(version: str, record: dict, taxonomy: dict) -> tuple[list[dict], dict | None, bool]:
    prompt = load_prompt(version)
    messages = render(prompt, record["text"], taxonomy)
    fmt = response_schema(taxonomy) if prompt.structured_output else None
    payload = {"model": llm.model_name(), "messages": messages, "temperature": 0.0}
    if fmt:
        payload["response_format"] = fmt
    sent = (llm.CACHE_DIR / f"{llm._cache_key(payload)}.json").exists()
    return messages, fmt, sent


def to_markdown(version: str, record: dict, messages: list[dict], fmt: dict | None, sent: bool) -> str:
    prompt = load_prompt(version)
    parts = [
        f"# {version}: {prompt.title}",
        "",
        f"Exactly what `{llm.model_name()}` received for test complaint `{record['id']}` "
        f"(gold label: `{record['product']}` / `{record['issue']}`).",
        "",
        "Verified against the API call cache: "
        + ("**yes, this exact request was sent.**" if sent else "not found in the local cache."),
        "",
        "## System message",
        "",
        "````text",
        messages[0]["content"],
        "````",
        "",
        "## User message",
        "",
        "````text",
        messages[1]["content"],
        "````",
    ]
    if fmt:
        parts += ["", "## response_format (Structured Outputs)", "", "```json", json.dumps(fmt, indent=2), "```"]
    return "\n".join(parts) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", help="test complaint id (default: first one in test.jsonl)")
    args = ap.parse_args()

    test = load_split("test")
    record = next(r for r in test if r["id"] == args.id) if args.id else test[0]
    taxonomy = load_taxonomy()
    OUT.mkdir(exist_ok=True)

    for v in list_versions():
        messages, fmt, sent = build(v, record, taxonomy)
        path = OUT / f"{v}.md"
        path.write_text(to_markdown(v, record, messages, fmt, sent), encoding="utf-8")
        print(f"{path.relative_to(ROOT)}  sent={'yes' if sent else 'NO'}")


if __name__ == "__main__":
    main()
