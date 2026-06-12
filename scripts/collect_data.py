"""
collect_data.py
---------------
CLI entry point for the two-phase Wikidata author data collection pipeline.

Usage examples (run from project root), e.g.:
    For 100 german authors: 
        uv run scripts/collect_data.py --country germany --limit 100 --max-pages 1 

    For 1.000 german authors: 
        uv run  scripts/collect_data.py --country germany --limit 500 --max-pages 2 

    For 10.000 german authors: 
        uv run scripts/collect_data.py --country germany --limit 500 --max-pages 20 
        
    For all german authors (roughly 28.000 as of 2026-06-12):
        uv run scripts/collect_data.py --country germany --all
        On Mac, prevent sleep during long runs with caffeinate:
        caffeinate -i uv run scripts/collect_data.py --country germany --all

Output:
    data/raw/{country}_authors_{n}_raw.json
    data/raw/{country}_authors_{n}_labels.json
"""


import argparse
import json
import math
from pathlib import Path
from datetime import date

from kg_dh import fetch_all_entities, fetch_author_qids_paged, resolve_labels
from kg_dh.queries import AUTHOR_QUERIES, MAX_AUTHORS

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect Wikidata author data and save to data/raw/"
    )
    parser.add_argument(
        "--country",
        choices=list(AUTHOR_QUERIES.keys()),
        required=True,
        help="Country corpus to collect (germany | uk | netherlands)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="QIDs per SPARQL page in Phase 1 (default: 500)",
    )
    # --max-pages and --all are mutually exclusive
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument(
        "--max-pages",
        type=int,
        default=1,
        help="Number of SPARQL pages to fetch (default: 1 = 500 authors)",
    )
    scope.add_argument(
        "--all",
        action="store_true",
        help="Fetch full corpus (requires MAX_AUTHORS to be set for country)",
    )
    return parser.parse_args()



def main() -> None:
    args = parse_args()

    # ── compute max_pages ─────────────────────────────────────────────────────
    if args.all:
        if MAX_AUTHORS[args.country] is None:
            raise ValueError(
                f"MAX_AUTHORS not set for '{args.country}'. "
                f"Run the estimate query on query.wikidata.org first."
            )
        max_pages = math.ceil(MAX_AUTHORS[args.country] / args.limit)
    else:
        max_pages = args.max_pages

    print(f"Collecting {args.country} authors: "
          f"limit={args.limit}, max_pages={max_pages} "
          f"(~{args.limit * max_pages} authors max)")

    # ── Phase 1: collect QIDs ─────────────────────────────────────────────────
    qids = fetch_author_qids_paged(
        country=args.country,
        limit=args.limit,
        max_pages=max_pages,
    )

    # ── Phase 2: fetch author properties ─────────────────────────────────────
    authors_df = fetch_all_entities(qids)

    # ── Phase 3: resolve claim QIDs to labels ────────────────────────────────
    label_lookup = resolve_labels(authors_df)


        # ── save outputs ──────────────────────────────────────────────────────────
    n = len(authors_df)

    # both files go to data/raw/, paired by country and author count
    raw_dir = Path("data/raw")
    raw_dir.mkdir(parents=True, exist_ok=True)

    # collection date appended to filename for traceability
    collected_on = date.today().strftime("%Y-%m-%d")

    raw_path   = raw_dir / f"{args.country}_authors_{n}_raw_{collected_on}.json"
    authors_df.to_json(raw_path, orient="records", indent=2)
    print(f"Saved {n} authors → {raw_path}")

    label_path = raw_dir / f"{args.country}_authors_{n}_labels_{collected_on}.json"
    with open(label_path, "w", encoding="utf-8") as f:
        json.dump(label_lookup, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(label_lookup)} labels → {label_path}")


if __name__ == "__main__":
    main()