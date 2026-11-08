"""Loads the versioned prompts from prompts/*.md and builds the chat messages.

File format:

    ---
    version: v2
    title: ...
    structured_output: false
    few_shot_ids: []          # dev ids used as examples (optional)
    ---
    # system
    ...text...
    # user
    ...text with {{text}}...

Available placeholders: {{products}}, {{issues}}, {{examples}}, {{text}}.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT / "prompts"
DATA_DIR = ROOT / "data"


@dataclass
class PromptVersion:
    version: str
    title: str
    system: str
    user: str
    structured_output: bool = False
    few_shot_ids: list[str] = field(default_factory=list)


def load_taxonomy() -> dict:
    return json.loads((DATA_DIR / "taxonomy.json").read_text(encoding="utf-8"))


def load_split(split: str) -> list[dict]:
    with open(DATA_DIR / f"{split}.jsonl", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def parse_prompt_file(raw: str) -> PromptVersion:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
    if not m:
        raise ValueError("Prompt file has no YAML front matter")
    meta = yaml.safe_load(m.group(1))
    body = m.group(2)
    sections = re.split(r"^# (system|user)\s*$", body, flags=re.M)
    parts = {sections[i]: sections[i + 1].strip() for i in range(1, len(sections) - 1, 2)}
    if "system" not in parts or "user" not in parts:
        raise ValueError("The prompt needs '# system' and '# user' sections")
    return PromptVersion(
        version=meta["version"],
        title=meta["title"],
        system=parts["system"],
        user=parts["user"],
        structured_output=bool(meta.get("structured_output", False)),
        few_shot_ids=[str(i) for i in meta.get("few_shot_ids") or []],
    )


def load_prompt(version: str) -> PromptVersion:
    matches = sorted(PROMPTS_DIR.glob(f"{version}_*.md"))
    if not matches:
        raise FileNotFoundError(f"No prompt found for {version} in {PROMPTS_DIR}")
    return parse_prompt_file(matches[0].read_text(encoding="utf-8"))


def list_versions() -> list[str]:
    return sorted({p.name.split("_")[0] for p in PROMPTS_DIR.glob("v*_*.md")}, key=lambda v: int(v[1:]))


def _format_examples(ids: list[str]) -> str:
    if not ids:
        return ""
    dev = {str(r["id"]): r for r in load_split("dev")}
    blocks = []
    for i, ex_id in enumerate(ids, 1):
        r = dev[ex_id]
        answer = json.dumps({"product": r["product"], "issue": r["issue"]}, ensure_ascii=False)
        blocks.append(f"Example {i}\nComplaint: {r['text']}\nAnswer: {answer}")
    return "\n\n".join(blocks)


def render(p: PromptVersion, text: str, taxonomy: dict) -> list[dict]:
    subs = {
        "{{products}}": "\n".join(f"- {x}" for x in taxonomy["products"]),
        "{{issues}}": "\n".join(f"- {x}" for x in taxonomy["issues"]),
        "{{examples}}": _format_examples(p.few_shot_ids),
        "{{text}}": text,
    }
    system, user = p.system, p.user
    for k, v in subs.items():
        system = system.replace(k, v)
        user = user.replace(k, v)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def response_schema(taxonomy: dict) -> dict:
    """Strict JSON Schema (Structured Outputs) used by versions with structured_output: true."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "complaint_triage",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "reasoning": {"type": "string"},
                    "product": {"type": "string", "enum": taxonomy["products"]},
                    "issue": {"type": "string", "enum": taxonomy["issues"]},
                    "resumo_pt": {"type": "string"},
                },
                "required": ["reasoning", "product", "issue", "resumo_pt"],
                "additionalProperties": False,
            },
        },
    }
