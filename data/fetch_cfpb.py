"""Builds the dev/test samples from the real CFPB consumer complaint database.

Why two sources?
- The official CFPB file (files.consumerfinance.gov/ccdb/complaints.csv.zip) no longer
  publishes the "Consumer complaint narrative" column (the complaint text).
- The text comes from a CC0 mirror of the same file on Hugging Face
  (BEE-spoke-data/consumer-finance-complaints, "has-text" config, extracted up to Jan 2024).
- Every sampled complaint is checked against the official file by Complaint ID:
  only cases whose product and issue match the current official record are kept.

Usage:
    python data/fetch_cfpb.py
"""

from __future__ import annotations

import json
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import requests

MIRROR_URL = (
    "https://huggingface.co/datasets/BEE-spoke-data/consumer-finance-complaints/"
    "resolve/refs%2Fconvert%2Fparquet/has-text/train/0002.parquet"
)
OFFICIAL_URL = "https://files.consumerfinance.gov/ccdb/complaints.csv.zip"

DATA_DIR = Path(__file__).resolve().parent
RAW = DATA_DIR / "raw"
MIRROR_FILE = RAW / "hf_0002.parquet"
OFFICIAL_FILE = RAW / "complaints.csv.zip"

SEED = 42
MIN_DATE = "2023-01-01"
MIN_CHARS, MAX_CHARS = 300, 3000  # too short has no signal; too long costs more
PER_CLASS_DEV, PER_CLASS_TEST = 15, 28
N_ISSUES = 10                     # most frequent issues become classes; the rest becomes "Other"

# Original CFPB product -> lab class (7 classes).
# In Apr 2023 the CFPB renamed some products; both spellings are mapped.
PRODUCT_MAP = {
    "Credit reporting, credit repair services, or other personal consumer reports": "credit_reporting",
    "Credit reporting or other personal consumer reports": "credit_reporting",
    "Debt collection": "debt_collection",
    "Checking or savings account": "bank_account",
    "Credit card or prepaid card": "credit_card",
    "Credit card": "credit_card",
    "Mortgage": "mortgage",
    "Money transfer, virtual currency, or money service": "money_transfer",
    "Student loan": "consumer_loan",
    "Vehicle loan or lease": "consumer_loan",
    "Payday loan, title loan, or personal loan": "consumer_loan",
    "Payday loan, title loan, personal loan, or advance loan": "consumer_loan",
}

COLS = {
    "Complaint ID": "id",
    "Date received": "date_received",
    "Product": "cfpb_product",
    "Issue": "cfpb_issue",
    "Consumer complaint narrative": "text",
}


def download(url: str, dest: Path) -> None:
    if dest.exists():
        print(f"Using already downloaded file: {dest.name}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url} ...")
    tmp = dest.with_suffix(".part")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    tmp.rename(dest)


def load_mirror() -> pd.DataFrame:
    df = pd.read_parquet(MIRROR_FILE, columns=list(COLS)).rename(columns=COLS)
    df = df.dropna(subset=["text"])
    df = df[(df["date_received"] >= MIN_DATE) & df["cfpb_product"].isin(PRODUCT_MAP)]
    n = df["text"].str.len()
    df = df[(n >= MIN_CHARS) & (n <= MAX_CHARS)].copy()
    df["id"] = df["id"].astype(str)
    return df


def load_official(ids: set[str]) -> pd.DataFrame:
    """Reads the official CFPB file, keeping only the IDs of interest."""
    parts = []
    with zipfile.ZipFile(OFFICIAL_FILE) as zf:
        with zf.open("complaints.csv") as fh:
            cols = ["Complaint ID", "Product", "Issue"]
            for chunk in pd.read_csv(fh, usecols=cols, dtype=str, chunksize=500_000):
                parts.append(chunk[chunk["Complaint ID"].isin(ids)])
    return pd.concat(parts).rename(
        columns={"Complaint ID": "id", "Product": "official_product", "Issue": "official_issue"}
    )


def main() -> None:
    download(MIRROR_URL, MIRROR_FILE)
    download(OFFICIAL_URL, OFFICIAL_FILE)

    df = load_mirror()
    print(f"Eligible complaints in the mirror: {len(df):,}")

    official = load_official(set(df["id"]))
    df = df.merge(official, on="id", how="left")
    found = df["official_product"].notna()
    agree = found & (df["cfpb_product"] == df["official_product"]) & (df["cfpb_issue"] == df["official_issue"])
    print(f"Found in official file: {found.mean():.1%} | identical labels: {agree.sum() / found.sum():.1%}")
    df = df[agree].copy()
    df["product"] = df["cfpb_product"].map(PRODUCT_MAP)
    print(df["product"].value_counts().to_string())

    per_class = PER_CLASS_DEV + PER_CLASS_TEST
    sample = (
        df.groupby("product", group_keys=False)
        .sample(n=per_class, random_state=SEED)
        .sample(frac=1, random_state=SEED)
        .reset_index(drop=True)
    )

    top_issues = sample["cfpb_issue"].value_counts().head(N_ISSUES).index
    sample["issue"] = sample["cfpb_issue"].where(sample["cfpb_issue"].isin(top_issues), "Other")

    dev_idx = sample.groupby("product", group_keys=False).sample(n=PER_CLASS_DEV, random_state=SEED).index
    sample["split"] = "test"
    sample.loc[dev_idx, "split"] = "dev"

    fields = ["id", "date_received", "text", "product", "issue", "cfpb_product", "cfpb_issue"]
    for split in ("dev", "test"):
        rows = sample[sample["split"] == split][fields].to_dict(orient="records")
        with open(DATA_DIR / f"{split}.jsonl", "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"{split}.jsonl: {len(rows)} cases")

    meta = {
        "text_source": MIRROR_URL,
        "label_source": OFFICIAL_URL,
        "extracted_on": date.today().isoformat(),
        "eligible_rows": int(found.sum()),
        "label_agreement_with_official": round(float(agree.sum() / found.sum()), 4),
        "filters": {"min_date": MIN_DATE, "min_chars": MIN_CHARS, "max_chars": MAX_CHARS},
        "seed": SEED,
        "products": sorted(set(PRODUCT_MAP.values())),
        "issues": sorted(top_issues) + ["Other"],
    }
    (DATA_DIR / "taxonomy.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print("taxonomy.json saved")


if __name__ == "__main__":
    main()
