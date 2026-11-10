"""Count how often each `member_of` and `award_received` Wikidata item occurs.

Reads the raw author JSON (list of dicts with Q-ID lists) and the Q-ID -> label
JSON, and writes frequency tables sorted by frequency (highest first) for manual
inspection.

Each item is counted at most once per author (a few authors list the same item
twice on Wikidata), so "n_authors" = number of distinct authors with that item.

Outputs (in --out-dir):
    member_award_frequencies.xlsx       one sheet per key + a summary sheet
    member_of_frequencies.csv
    award_received_frequencies.csv

Usage (from repo root):
    uv run python scripts/extract_member_award_frequencies.py \
        --raw data/raw/netherlands_authors_6970_raw_2026-08-28.json \
        --labels data/raw/netherlands_authors_6970_labels_2026-08-28.json \
        --out-dir data/interim
"""

import argparse
import json
from collections import Counter
from pathlib import Path

import pandas as pd

KEYS = ["member_of", "award_received"]


def count_key(authors: list[dict], key: str) -> tuple[Counter, int]:
    """Return (Counter of Q-ID -> n_authors, n authors with >=1 value)."""
    counter: Counter = Counter()
    n_with_value = 0
    for author in authors:
        values = set(author.get(key) or [])  # set -> count once per author
        if values:
            n_with_value += 1
            counter.update(values)
    return counter, n_with_value


TYPE_COLUMNS = {"member_of": "type_of_membership", "award_received": "type_of_award"}


def build_table(
    counter: Counter, labels: dict[str, str], n_authors: int, n_with_value: int, key: str
) -> pd.DataFrame:
    df = pd.DataFrame(counter.items(), columns=["qid", "n_authors"])
    df["label"] = df["qid"].map(labels).fillna("")  # empty = label missing
    df["pct_of_all_authors"] = (df["n_authors"] / n_authors * 100).round(2)
    df["pct_of_authors_with_value"] = (df["n_authors"] / n_with_value * 100).round(2)
    df["wikidata_url"] = "https://www.wikidata.org/wiki/" + df["qid"]
    df[TYPE_COLUMNS[key]] = ""  # empty column for manual annotation
    # frequency desc, label asc as a stable tie-breaker
    df = df.sort_values(["n_authors", "label"], ascending=[False, True]).reset_index(drop=True)
    df.insert(0, "rank", df.index + 1)
    return df[
        ["rank", "qid", "label", "n_authors", "pct_of_all_authors",
         "pct_of_authors_with_value", "wikidata_url", TYPE_COLUMNS[key]]
    ]


def write_excel(path: Path, tables: dict[str, pd.DataFrame], summary: pd.DataFrame) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="summary", index=False)
        for key, df in tables.items():
            df.to_excel(writer, sheet_name=key, index=False)
        for ws in writer.book.worksheets:
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for col in ws.columns:
                width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
                ws.column_dimensions[col[0].column_letter].width = min(width + 2, 70)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--raw", type=Path, required=True, help="raw authors JSON")
    p.add_argument("--labels", type=Path, required=True, help="Q-ID -> label JSON")
    p.add_argument("--out-dir", type=Path, default=Path("data/interim"))
    args = p.parse_args()

    authors = json.loads(args.raw.read_text(encoding="utf-8"))
    labels = json.loads(args.labels.read_text(encoding="utf-8"))
    n_authors = len(authors)

    tables, summary_rows = {}, []
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for key in KEYS:
        counter, n_with_value = count_key(authors, key)
        df = build_table(counter, labels, n_authors, n_with_value, key)
        tables[key] = df
        df.to_csv(args.out_dir / f"{key}_frequencies.csv", index=False, encoding="utf-8-sig")
        summary_rows.append({
            "key": key,
            "n_authors_total": n_authors,
            "n_authors_with_value": n_with_value,
            "n_unique_items": len(df),
        })
        print(f"{key}: {n_with_value}/{n_authors} authors have a value, {len(df)} unique items")

    write_excel(args.out_dir / "member_award_frequencies.xlsx", tables, pd.DataFrame(summary_rows))
    print(f"Written to {args.out_dir}")


if __name__ == "__main__":
    main()