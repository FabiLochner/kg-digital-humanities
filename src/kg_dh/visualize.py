""" 

visualize.py
-----------

Pyvis rendering and GEphi expoert for the author KG.
Takes a networkx DiGraph from graph.py and procudes:
    - Interactive HTML via pyvis (for <= 3.000 nodes)
    - GEXF file for Gephi visualization (for > 3.000 nodes)

Workflow:
    G = build_graph(...)    # graph.py
    G = prepare_nx_for_pyvis(G) # enriches G with color/size/tooltip attributes
    net = build_pyvis()     # wraps into pyvis network
    save_html_with_overlays(net, path, G)    # saves HTML + injects legend and stats
    build_gephi_gexf(G, path)    # build GEXF file for Gephi export 

"""

# 1) import libraries
# general
from pathlib import Path
import networkx as nx
from pyvis.network import Network
# from graph.py
from kg_dh.graph import EDGE_TYPE_PROPS

# 2) config settings 

## 2.1) colors

#  define color schemes by node type
NODE_COLORS: dict[str, str] = {
    "author":         "#4A90D9",  # blue        — author nodes
    "place_birth":    "#7FB069",  # green       — birth places
    "award_received": "#E8C547",  # gold        — awards
    "educated_at":    "#1ABC9C",  # teal        — education institutions
    "field_of_work":  "#E67E22",  # orange      — fields of work
    "genre":          "#F0A830",  # amber-orange — genres (same family as field_of_work)
    "member_of":      "#9B59B6",  # purple      — organisations/academies
    "movement":       "#E74C3C",  # red         — literary movements
    "influenced_by":  "#C0392B",  # dark red    — influences (same family as movement)
}


# edge colours match their target node type for visual coherence
EDGE_COLORS: dict[str, str] = {
    k: v for k, v in NODE_COLORS.items() if k != "author"
}

## 2.2) pixel sizes

# author nodes: fixed uniform size — avoids data-completeness bias
# (an author with more Wikidata properties would otherwise appear larger)
AUTHOR_NODE_SIZE: int = 15

# entity nodes: scaled by in-degree (number of authors connected to them)
MIN_ENTITY_SIZE: int = 8
MAX_ENTITY_SIZE: int = 50

# maximum label length shown on node
MAX_LABEL_LENGTH: int = 25


## 2.3) displayed network statistics
# number of top entities shown per type in the stats panel
TOP_N: int = 5


# 3) write functions 


def build_hover_tooltip(node_id: str, node_data: dict) -> str:
    """
    Build an HTML tooltip string shown on node hover in pyvis.
    Author nodes show all demographic attributes.
    Entity nodes show type and label.
    The title attribute in pyvis/vis.js renders HTML directly.
    """
    node_type = node_data.get("node_type", "unknown")
    label = node_data.get("label", node_id)

    if node_type == "author":
        lines = [
            f"<b>{label}</b>",
            f"{node_id}",
            "<hr>",
            f"<b>Sex/gender:</b> {node_data.get('sex_gender', 'n/a')}",
            f"<b>Citizenship:</b> {node_data.get('citizenship', 'n/a')}",
            f"<b>Birth year:</b> {node_data.get('birth_year', 'n/a')}",
            f"<b>Death year:</b> {node_data.get('death_year', 'n/a')}",
            f"<b>Writing language:</b> {node_data.get('writing_language', 'n/a')}",
            f"<b>Occupation:</b> {node_data.get('occupation', 'n/a')}",
        ]
    else:
        lines = [
            f"<b>{label}</b>",
            f"{node_id}",
            f"<b>Type:</b> {node_type.replace('_', ' ')}",
        ]
    return "<br>".join(lines)


def scale_size(in_degree: int, min_degree: int, max_degree: int) -> int:
    """ 
    Scale an entity node's ini-degree to a pixel size in 
    [MIN_ENTITY_SIZE, MAX_ENTITY_SIZE].
    In-degree = number of authors connected to this entity node.
    Entity nodes shared by more authors appear visually larger (e.g., movements, genres, awards, education institutions)
    Author nodes are not scaled - they use fixed AUTHOR_NODE_SIZE.    
    """

    if max_degree == min_degree:
        return MIN_ENTITY_SIZE
    
    # Step 1: convert the raw in-degree to a value between 0.0 and 1.0
    # — the entity with the fewest connections gets ratio = 0.0
    # — the entity with the most connections gets ratio = 1.0
    # — everything else lands proportionally in between
    # e.g. min=1, max=29, in_degree=15 → ratio = (15-1)/(29-1) = 0.5
    ratio = (in_degree - min_degree) / (max_degree - min_degree)

    # Step 2: map that 0.0–1.0 ratio onto the pixel size range
    # — ratio=0.0 → MIN_ENTITY_SIZE (e.g. 8px,  least connected entity)
    # — ratio=1.0 → MAX_ENTITY_SIZE (e.g. 50px, most connected entity)
    # — ratio=0.5 → midpoint        (e.g. 29px, average connectivity)
    return int(MIN_ENTITY_SIZE + ratio * (MAX_ENTITY_SIZE - MIN_ENTITY_SIZE))


def prepare_nx_for_pyvis(G: nx.DiGraph) -> nx.DiGraph:
    """ 
    Enrich networkx node and edge attributes with pyvis display properties.
    Must be called before build_pyvis(). Modifies G in place and returns it.

    Sets on each node:
        color  — by node_type (see NODE_COLORS)
        size   — author nodes: fixed AUTHOR_NODE_SIZE (uniform across all authors)
                 entity nodes: scaled by in-degree to [MIN_ENTITY_SIZE, MAX_ENTITY_SIZE]
                 in-degree = number of authors pointing to this entity, making
                 shared awards/movements/institutions visually prominent
        title  — HTML hover tooltip with all attributes
        label  — truncated display label (max MAX_LABEL_LENGTH chars)

    Sets on each edge:
        color  — by relation type (see EDGE_COLORS)
        title  — relation type shown on edge hover
    
    
    """

    # compute in-degree only for entity nodes (all edges flow author → entity,
    # so entity in-degree = number of authors connected to that entity)

    entity_in_degrees = {
        n: G.in_degree(n)
        for n, d in G.nodes(data = True)
        if d.get("node_type") != "author"
    }
    min_in_degree = min(entity_in_degrees.values()) if entity_in_degrees else 0
    max_in_degree = max(entity_in_degrees.values()) if entity_in_degrees else 1

    for node_id, data in G.nodes(data = True):
        node_type = data.get("node_type", "unknown")

        # colour by node type
        # fallback grey for any node_type not defined in NODE_COLORS
        # visible against the dark background without clashing with defined colours
        G.nodes[node_id]["color"] = NODE_COLORS.get(node_type, "#888888")

        # author nodes: uniform fixed size
        # entity nodes: scaled by in-degree — more shared = visually larger
        if node_type == "author":
            G.nodes[node_id]["size"] = AUTHOR_NODE_SIZE
        else:
            G.nodes[node_id]["size"] = scale_size(
                entity_in_degrees[node_id], min_in_degree, max_in_degree
            )

        # truncate long labels for readability
        raw_label = data.get("label", node_id)
        G.nodes[node_id]["label"] = (
            raw_label[:MAX_LABEL_LENGTH] + "…"
            if len(raw_label) > MAX_LABEL_LENGTH
            else raw_label
        )

    for src, tgt, data in G.edges(data = True):
        relation = data.get("relation", "unknown")
        # edge colour matches target node type (if not available, also grey backfall)
        G.edges[src, tgt]["color"] = EDGE_COLORS.get(relation, "#888888")
        # label shown on edge hover
        G.edges[src, tgt]["title"] = relation.replace("_", " ")

    return G


def build_pyvis(
    G: nx.DiGraph,
    height: str = "900px",
    width: str = "100%",
) -> Network:
    """
    Build a pyvis Network from a pyvis-prepared NetworkX DiGraph.
    Call prepare_nx_for_pyvis(G) first.

    Features enabled:
        directed=True     — arrows show edge direction
        filter_menu=True  — attribute filter panel (filter by node_type etc.)
        barnes_hut()      — force-directed physics, handles heterogeneous graphs
                            better than the default repulsion model

    """ 
    net = Network(
        height = height,
        width=width,
        bgcolor = "#1a1a2e",   # dark background — nodes pop visually
        font_color = "white",
        directed=True, #directed graph
        select_menu=False,  # removed: showed QIDs not labels, not useful
        filter_menu= True, #ability to filter nodes and edges based on attributes
        cdn_resources="in_line" # embed vis.js directly - no internet needed to open
    )

    # from_nx translates networkx attributes (title, color, size, label)
    # directly to vis.js node properties - no manual re-mapping needed
    net.from_nx(G)

    # set HTML tooltips directly on pyvis nodes after from_nx —
    # from_nx does not reliably pass HTML through to vis.js
    for node in net.nodes:
        node_id = node["id"]
        node_data = G.nodes[node_id]
        node["title"] = build_hover_tooltip(node_id, node_data)

    # use barnes_hut as physics for KG:
    # gravity pulls unconnected clusters together while edges push aprt
    net.barnes_hut()

    return net


def build_legend_html(
    node_colors: dict[str, str],
    active_node_types: set[str],
) -> str:
    """
    Build HTML for the node type colour legend overlay.
    Only shows node types actually present in the graph.
    Positioned fixed at bottom-left of the browser window.
    """
    items = []
    for node_type, color in node_colors.items():
        if node_type not in active_node_types:
            # skip types not present in this graph
            continue
        label = node_type.replace("_", " ").title()
        items.append(
            f'<div style="display:flex;align-items:center;margin:4px 0;">'
            f'<div style="width:13px;height:13px;background:{color};'
            f'border-radius:50%;margin-right:8px;flex-shrink:0;"></div>'
            f'<span>{label}</span>'
            f'</div>'
        )

    items_html = "\n".join(items)
    return f"""
    <div id="kg-legend" style="
        position:fixed; bottom:20px; left:20px;
        background:rgba(26,26,46,0.92);
        color:white; padding:12px 16px; border-radius:8px;
        font-family:Arial,sans-serif; font-size:13px;
        z-index:1000; min-width:180px;
        border:1px solid rgba(255,255,255,0.15);
    ">
        <div style="font-weight:bold;margin-bottom:8px;font-size:14px;">
            Node Types
        </div>
        {items_html}
    </div>
    """



def compute_top_entities_per_type(
    G: nx.DiGraph,
    top_n: int = TOP_N,
) -> dict[str, list[dict]]:
    """
    For each entity type present in the graph, return the top-N nodes
    by in-degree (number of authors connected to them).

    Returns dict keyed by entity type, values are lists of
    {label, in_degree} dicts sorted descending by in_degree.
    Preserves EDGE_TYPE_PROPS ordering for consistent display.
    """
    results = {}
    for edge_type in EDGE_TYPE_PROPS:
        # collect nodes of this type present in the graph
        nodes_of_type = [
            n for n, d in G.nodes(data=True)
            if d.get("node_type") == edge_type
        ]
        if not nodes_of_type:
            # skip types with no nodes in this graph
            continue

        # sort by in-degree descending, take top N
        top_nodes = sorted(
            nodes_of_type,
            key=lambda n: G.in_degree(n),
            reverse=True,
        )[:top_n]

        results[edge_type] = [
            {
                "label":     G.nodes[n].get("label", n),
                "in_degree": G.in_degree(n),
            }
            for n in top_nodes
        ]
    return results


def build_stats_html(
    top_entities_per_type: dict[str, list[dict]],
    node_colors: dict[str, str],
    top_n: int = TOP_N,
) -> str:
    """
    Build HTML for the top-N entities per type stats panel overlay.
    Shows entity label and in-degree (number of connected authors) per type.
    Positioned fixed at bottom-right of the browser window, scrollable.
    """
    sections = []
    for entity_type, entities in top_entities_per_type.items():
        if not entities:
            continue
        color      = node_colors.get(entity_type, "#888888")
        type_label = entity_type.replace("_", " ").title()

        # build table rows for this entity type
        rows_html = ""
        for rank, entry in enumerate(entities, start=1):
            rows_html += (
                f'<tr>'
                f'<td style="padding:2px 6px;color:#aaa;">{rank}</td>'
                f'<td style="padding:2px 6px;">{entry["label"]}</td>'
                f'<td style="padding:2px 6px;text-align:center;'
                f'color:#E8C547;">{entry["in_degree"]}</td>'
                f'</tr>'
            )

        sections.append(f"""
        <div style="margin-bottom:14px;">
            <div style="display:flex;align-items:center;margin-bottom:5px;">
                <div style="width:10px;height:10px;background:{color};
                    border-radius:50%;margin-right:7px;"></div>
                <span style="font-weight:bold;font-size:12px;">{type_label}</span>
            </div>
            <table style="width:100%;border-collapse:collapse;font-size:12px;">
                <tr style="color:#aaa;border-bottom:1px solid #444;">
                    <th style="padding:2px 6px;text-align:left;">#</th>
                    <th style="padding:2px 6px;text-align:left;">Entity</th>
                    <th style="padding:2px 6px;text-align:center;">Authors</th>
                </tr>
                {rows_html}
            </table>
        </div>
        """)

    sections_html = "\n".join(sections)
    return f"""
    <div id="kg-stats" style="
        position:fixed; bottom:20px; right:20px;
        background:rgba(26,26,46,0.92);
        color:white; padding:12px 16px; border-radius:8px;
        font-family:Arial,sans-serif; font-size:13px;
        z-index:1000; max-width:260px;
        max-height:60vh; overflow-y:auto;
        border:1px solid rgba(255,255,255,0.15);
    ">
        <div style="font-weight:bold;margin-bottom:10px;font-size:14px;">
            Top {top_n} per Entity Type
        </div>
        {sections_html}
    </div>
    """


def inject_into_html(html_path: Path, *html_snippets: str) -> None:
    """
    Inject one or more HTML snippets before the closing </body> tag
    of an existing HTML file. Modifies the file in place.
    """
    content = html_path.read_text(encoding="utf-8")
    injection = "\n".join(html_snippets)
    # insert overlays just before </body> so they render on top of the graph
    content = content.replace("</body>", f"{injection}\n</body>")
    html_path.write_text(content, encoding="utf-8")



def save_html_with_overlays(
    net: Network,
    output_path: str | Path,
    G: nx.DiGraph,
    node_colors: dict[str, str] = NODE_COLORS,
    top_n: int = TOP_N,
) -> None:
    """
    Save pyvis Network to a self-contained HTML file, then inject:
      - Colour legend (bottom-left): shows node type → colour mapping
      - Stats panel (bottom-right): top-N entities per type by in-degree

    Only node types actually present in the graph appear in the overlays.
    The colleague can open the HTML directly — no internet or server needed.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1) save base pyvis HTML
    net.save_graph(str(output_path))

    # 2) build legend — only for node types present in this graph
    active_node_types = {
        d.get("node_type")
        for _, d in G.nodes(data=True)
        if d.get("node_type")
    }
    legend_html = build_legend_html(node_colors, active_node_types)

    # 3) build stats panel — top-N per entity type by in-degree
    top_entities = compute_top_entities_per_type(G, top_n=top_n)
    stats_html   = build_stats_html(top_entities, node_colors, top_n=top_n)

    # 4) inject both overlays into the saved HTML in one pass
    inject_into_html(output_path, legend_html, stats_html)

    print(f"Saved visualization → {output_path}")


def build_gephi_export(G: nx.DiGraph, output_path: str | Path) -> None:
    """
    Export the NetworkX DiGraph to GEXF format for Gephi.
    Used for graphs with 3,000+ nodes where pyvis becomes sluggish.
    Note: list-type node attributes are converted to strings for GEXF compatibility.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # GEXF requires all attributes to be simple types (str, int, float)
    # list attributes from the raw data are already resolved to strings in build_graph()
    nx.write_gexf(G, str(output_path))
    print(f"Saved Gephi export → {output_path}")



