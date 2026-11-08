"""Tests that run without an API key."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from metrics import classification_metrics, normalize_label, parse_output  # noqa: E402
from prompts import list_versions, load_prompt, load_split, load_taxonomy, parse_prompt_file, render  # noqa: E402


@pytest.mark.parametrize(
    "content",
    [
        '{"product": "mortgage"}',
        '```json\n{"product": "mortgage"}\n```',
        'Here is the answer: {"product": "mortgage"} hope it helps',
    ],
)
def test_parse_output_tolerates_wrappers(content):
    assert parse_output(content) == {"product": "mortgage"}


def test_parse_output_invalid():
    assert parse_output("no json here") is None
    assert parse_output("[1, 2]") is None


def test_normalize_label():
    allowed = ["credit_card", "Fraud or scam"]
    assert normalize_label("  CREDIT_CARD ", allowed) == "credit_card"
    assert normalize_label("fraud  or scam", allowed) == "Fraud or scam"
    assert normalize_label("credit card", allowed) is None
    assert normalize_label(None, allowed) is None


def test_invalid_prediction_counts_as_error():
    m = classification_metrics(["a", "b"], ["a", None], ["a", "b"])
    assert m["accuracy"] == 0.5
    assert m["off_taxonomy_rate"] == 0.5


def test_parse_prompt_file():
    raw = "---\nversion: v9\ntitle: T\n---\n# system\nS {{products}}\n# user\nU {{text}}\n"
    p = parse_prompt_file(raw)
    assert (p.version, p.system, p.user) == ("v9", "S {{products}}", "U {{text}}")


def test_all_prompts_render_and_have_placeholder():
    tax = load_taxonomy()
    for v in list_versions():
        p = load_prompt(v)
        msgs = render(p, "COMPLAINT_TEXT", tax)
        assert "COMPLAINT_TEXT" in msgs[1]["content"], v
        assert "{{" not in msgs[0]["content"] + msgs[1]["content"], v


def test_few_shot_examples_come_from_dev_only():
    test_ids = {r["id"] for r in load_split("test")}
    dev_ids = {r["id"] for r in load_split("dev")}
    for v in list_versions():
        ids = set(load_prompt(v).few_shot_ids)
        assert ids <= dev_ids, v
        assert not ids & test_ids, v


def test_splits_are_disjoint_and_balanced():
    dev, test = load_split("dev"), load_split("test")
    assert not {r["id"] for r in dev} & {r["id"] for r in test}
    tax = load_taxonomy()
    for split in (dev, test):
        counts = {p: sum(r["product"] == p for r in split) for p in tax["products"]}
        assert len(set(counts.values())) == 1
