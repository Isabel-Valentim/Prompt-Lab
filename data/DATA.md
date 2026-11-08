# Data

## Source
**CFPB Consumer Complaint Database**: real complaints that US consumers filed with the Consumer Financial Protection Bureau. Public domain.

| What | Where from |
|---|---|
| Complaint text | CC0 mirror on Hugging Face: [`BEE-spoke-data/consumer-finance-complaints`](https://huggingface.co/datasets/BEE-spoke-data/consumer-finance-complaints), `has-text` config, shard `0002.parquet` |
| Labels (product and issue) | Official CFPB file: `files.consumerfinance.gov/ccdb/complaints.csv.zip` |

**Why two sources:** the official CFPB file no longer publishes the *Consumer complaint narrative* column, which holds the text. The mirror has the text, but it is a third-party copy. So every complaint is **checked against the official file by Complaint ID**: 99.9% were found, and **100% of those have the same product and issue** as the official record.

## Filters
- Complaints received from 2023-01-01 onward (the mirror ends on 2024-01-10).
- Text between 300 and 3,000 characters.
- 7 products (below). Prepaid card and debt management were left out because they have too few cases.
- Result: 73,655 eligible complaints.

## Sample
- Stratified: 43 complaints per product (seed 42).
- `dev.jsonl`: 105 cases (15 per product), used to iterate on prompts and pick examples.
- `test.jsonl`: 196 cases (28 per product), used only for the final evaluation.

## Taxonomy
**Product** (7 classes, merging CFPB names that changed in April 2023):

| Class | CFPB products |
|---|---|
| credit_reporting | Credit reporting (both spellings) |
| debt_collection | Debt collection |
| bank_account | Checking or savings account |
| credit_card | Credit card; Credit card or prepaid card |
| mortgage | Mortgage |
| money_transfer | Money transfer, virtual currency, or money service |
| consumer_loan | Student loan; Vehicle loan or lease; Payday/title/personal loan |

**Issue** (11 classes): the 10 most frequent issues in the sample, plus `Other`. See [`taxonomy.json`](taxonomy.json).

## Limitations
- **The label is chosen by the consumer** on the CFPB form, not by an analyst. A complaint about a late payment on a credit report may have been filed as "Credit card". That puts the accuracy ceiling below 100%.
- Personal data in the texts is redacted as `XXXX` by the CFPB itself.
- Texts are in English. The prompts are in English and the summary is generated in Brazilian Portuguese.

## Reproduce
```bash
python data/fetch_cfpb.py   # downloads ~670 MB into data/raw/ (git-ignored) and rebuilds dev/test/taxonomy
```
