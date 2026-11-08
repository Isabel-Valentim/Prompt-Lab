# Prompt CHANGELOG

Each version was written by looking **only at the previous version's errors on dev** (105 cases).
The test set (196 cases) was run only once at the end, for all versions.
Model: `gpt-4o-mini`, temperature 0.

| Version | Product (acc) | Issue (acc) | Issue (macro F1) | Tokens/case |
|---|---|---|---|---|
| v1 | 79.0% | 21.9% | 0.211 | 451 |
| v2 | 76.2% | 56.2% | 0.489 | 857 |
| v3 | 78.6% | 52.0% | 0.486 | 1910 |
| v4 | 80.0% | 45.7% | 0.435 | 1112 |
| v5 | **81.9%** | **57.1%** | **0.599** | 1520 |

*(dev; for v3, the 7 cases used as examples are excluded from scoring, n=98)*

---

## v1: zero-shot baseline
**What it is:** "classify this complaint", plus the label list and nothing else.

**What the errors showed:**
- The model **never picked "Other"**, even though it is the label for about 40% of cases.
- It picked issues that don't exist for the product: "Fraud or scam" for credit cards, "Dealing with your lender" for mortgages.
- Checking the data: **in the CFPB taxonomy, each issue belongs to a single product**. The model had no way of knowing that.

## v2: role + defined taxonomy
**Hypothesis:** if the model knows what each product means and which issues are valid for each product, it will stop mixing them up.

**Change:** a triage-analyst role, a definition for each product, an issue → product compatibility table, and a note that "Other" is common.

**Result:** issue accuracy went from **21.9% to 56.2%**. Product accuracy dropped by 3 cases, which is within noise at n=105.

**Remaining errors:** product boundaries (debt collection vs. credit reporting; transfer app vs. bank account). Reading the texts, I realized the CFPB label is **chosen by the consumer** on the form, so some of these cases are genuinely ambiguous.

## v3: boundary few-shot
**Hypothesis:** real examples of boundary cases teach the rule better than a definition.

**Change:** 7 dev examples (one per product) picked from v2's errors, plus 4 rules derived from them.

**Result:** **no improvement** (product 78.6%, issue 52.0%), and cost **more than doubled** (857 → 1,910 tokens per case).
**Decision:** dropped. v4 builds on v2, not v3.

## v4: v2 + Structured Outputs + short reasoning
**Hypothesis:** a JSON Schema with `enum` guarantees valid labels, and asking for short reasoning before the label ("who is the complaint against? what product did that company provide?") improves the boundaries.

**Change:** `response_format` with a strict JSON Schema and a `reasoning` field before `product` and `issue`.

**Result:** best product accuracy so far (**80.0%**), but issue accuracy **dropped to 45.7%**.
**Why:** the reasoning step led the model to *justify* a specific issue instead of admitting "Other". "Dealing with your lender" (student loans only) started showing up for car loans.

## v5: issue definitions + edge cases
**Hypothesis:** reasoning helps with the product, but it needs clear criteria for the issue.

**Change:**
- A definition for each issue, including "when NOT to use it".
- "Start from Other and switch only if the definition clearly matches."
- "Dealing with your lender" marked as **student loans only**.
- A "who is the complaint against" rule for product boundaries, e.g. a card issuer reporting late payments → credit_card.
- Edge cases: several problems in one complaint, and "XXXX" redacted data (never guess what's behind it).

**Result:** best version on every metric: product **81.9%**, issue **57.1%**, issue F1 **0.599** (up from 0.211 in v1).

**What it still gets wrong:** "Other" is still under-predicted (19 predictions vs. 42 in the dev gold labels), and transfer app vs. bank account remains ambiguous. I stopped here to avoid overfitting the prompt to dev.
