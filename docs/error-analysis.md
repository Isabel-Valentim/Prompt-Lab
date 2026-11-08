# Error analysis (v5 on test, n=196)

Numbers taken from [`results/v5_test.json`](../results/v5_test.json).

## Product: 81.6% accuracy

Accuracy by product:

| Product | Accuracy |
|---|---|
| credit_reporting | 100% |
| mortgage | 100% |
| bank_account | 93% |
| consumer_loan | 93% |
| money_transfer | 64% |
| debt_collection | 61% |
| credit_card | 61% |

Most frequent confusions:

| Gold → Predicted | Cases | What happens |
|---|---|---|
| money_transfer → bank_account | 8 | Scams where the money left a bank account. The consumer filed it as a "transfer", but the text is about the bank. |
| debt_collection → credit_reporting | 6 | The consumer finds the collection on their credit report and writes as if complaining about the report. |
| credit_card → consumer_loan / credit_reporting | 7 | Store cards and credit lines, or late payments reported to a bureau. |

Real example (id 6738291, gold money_transfer, predicted bank_account):
> "The XXXX recipient called from a Wells Fargo number, the one that was on the back of my debit card. They were reporting fraudulent transactions on my account..."

Reading the text, bank_account is a reasonable answer. **The CFPB label is chosen by the consumer**, so some of these "errors" come from ambiguous gold labels, not from the model.

## Issue: 56.6% accuracy (macro F1 0.585)

The dominant error is always the same: **"Other" is under-predicted**. In the gold labels, 90 of the 196 cases are "Other". v5 predicted "Other" only 40 times.

| Gold → Predicted | Cases |
|---|---|
| Other → Problem with a lender or other company charging your account | 14 |
| Other → Incorrect information on your report | 9 |
| Other → Attempts to collect debt not owed | 7 |
| Other → Managing an account | 6 |

The cause is structural: "Other" bundles dozens of real CFPB issues (e.g., *Closing an account*, *Communication tactics*, *Problem with a company's investigation*). Many of them sit right next to a specific label, and the model prefers the label that "looks" right.

## Portuguese summary (LLM-as-judge)
- v1 scored 3.68/5: one-sentence summaries that didn't say what the consumer wants.
- From v2 on, the instruction "two sentences: what happened and what the consumer wants" brought the score to about 4.2.
- **Limitation:** the judge is the same model (`gpt-4o-mini`), and it flagged 0% hallucination in every version. I don't treat that as proof that there are no hallucinations. The next step would be a larger judge model and a hand-reviewed sample.

## Next steps (not done, to avoid overfitting to dev)
1. Classify in **two stages**: first the product, then the issue, offering only that product's options plus definitions of the sub-issues that fall under "Other".
2. Measure **human agreement** on 50 cases to find the real ceiling, given that the label comes from the consumer.
3. Send only low-confidence cases to a larger model (cost-based routing).
