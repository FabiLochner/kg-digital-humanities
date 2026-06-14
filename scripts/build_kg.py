"""
build_kg.py
-----------
CLI entry point for KG construction and visualization.

Usage examples (run from project root):
    # 100 authors, all edge types, HTML
    uv run scripts/build_kg.py \
        --input data/raw/germany_authors_100_raw_2026-06-12.json \
        --labels data/raw/germany_authors_100_labels_2026-06-12.json \
        --edge-types all \
        --output-format html

    # 100 authors, filtered edge types only, HTML (for comparison)
    uv run scripts/build_kg.py \
        --input data/raw/germany_authors_100_raw_2026-06-12.json \
        --labels data/raw/germany_authors_100_labels_2026-06-12.json \
        --edge-types influenced_by,movement,member_of,field_of_work \
        --output-format html

    # 3000 authors, filtered, remove low-degree nodes, HTML
    uv run scripts/build_kg.py \
        --input data/raw/germany_authors_3000_raw_2026-06-12.json \
        --labels data/raw/germany_authors_3000_labels_2026-06-12.json \
        --edge-types influenced_by,movement,member_of \
        --min-degree 2 \
        --output-format html

    # 10000 authors, Gephi export
    uv run scripts/build_kg.py \
        --input data/raw/germany_authors_10000_raw_2026-06-12.json \
        --labels data/raw/germany_authors_10000_labels_2026-06-12.json \
        --edge-types all \
        --output-format gexf

Output:
    results/graphs/{input_stem}_kg_{edge-types}_{date}.html
    results/graphs/{input_stem}_kg_{edge-types}_{date}_stats.json
"""


# 1) import libraries
# general
import argparse
import json
from pathlib import Path
# KG construction
from kg_dh.graph import (
    EDGE_TYPE_PROPS,
    build_graph,
    filter_graph,
    load_data
)
# KG visualization
from kg_dh.visualize import (
    build_pyvis,
    prepare_nx_for_pyvis,
    save_html_with_overlays,
    build_gephi_export,
)


# 2) arg parse function

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and visualize the author knowledge graph."
    )
    parser.add_argument(
        "--input", required=True,
        help="Path to raw authors JSON (data/raw/...raw.json)",
    )
    parser.add_argument(
        "--labels", required=True,
        help="Path to labels JSON (data/raw/...labels.json)",
    )
    parser.add_argument(
        "--edge-types", default="all",
        help=(
            f"'all' or comma-separated subset of: {','.join(EDGE_TYPE_PROPS)}"
        ),
    )
    parser.add_argument(
        "--min-degree", type=int, default=1,
        help="Remove nodes with degree < min-degree (default: 1 = keep all)",
    )
    parser.add_argument(
        "--output-format", choices=["html", "gexf"], default="html",
        help="html = pyvis interactive (≤2k nodes); gexf = Gephi (large graphs)",
    )
    parser.add_argument(
        "--output-dir", default="results/graphs",
        help="Output directory (default: results/graphs/)",
    )
    return parser.parse_args()


# 3) main function to run script

def main() -> None:
    # 1) set args
    args = parse_args()

    # 2) parse edge types
    edge_types = (
        "all" if args.edge_types == "all"
        else args.edge_types.split(",")
    )

    # 3) load data
    print(f"Loading {args.input}...")
    authors, labels = load_data(args.input, args.labels)
    print(f"{len(authors)} authors | {len(labels)} labels")

    # 4) build KG
    print("Building knowledge graph...")
    G = build_graph(authors, labels, edge_types=edge_types)
    print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    # 5) optional degree filter
    if args.min_degree > 1:
        G = filter_graph(G, min_degree=args.min_degree)
        print(f"After filter (min_degree={args.min_degree}): "
              f"{G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
        
    # 6) build output filename 
    # date is extracted from the input filename, not today's date —
    # ensures the output KG is clearly traceable to its source data file
    input_stem = Path(args.input).stem.replace("_raw", "")
    edge_label = "all" if edge_types == "all" else "-".join(edge_types)
    out_stem   = f"{input_stem}_kg_{edge_label}"
    out_dir    = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 7) graph visualization or export
    if args.output_format == "html":
        print("Building pyvis visualization...")
        G = prepare_nx_for_pyvis(G)
        net = build_pyvis(G)
        save_html_with_overlays(net, out_dir / f"{out_stem}.html")

    elif args.output_format == "gexf":
        print("Exporting to Gephi GEXF...")
        build_gephi_export(G, out_dir / f"{out_stem}.gexf")

    
if __name__ == "__main__":
    main()