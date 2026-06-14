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
    save_html(net, path)    # writes HTML file
    build_gephi_gexf(G, path)    # build GEXF file for Gephi export 

"""

# 1) import libraries
from pathlib import Path
import networkx as nx
from pyvis.network import Network

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
            f"<i style='color:#aaa'>{node_id}</i>",
            "<hr style='border-color:#444'>",
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
            f"<i style='color:#aaa'>{node_id}</i>",
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
    return int(MIN_ENTITY_SIZE + ratio * ())


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
        NODE_COLORS.get(node_type, "#888888")

        # author nodes: uniform fixed size
        # entity nodes: scaled by in-degree — more shared = visually larger
        if node_type == "author":
            G.nodes[node_id]["size"] = AUTHOR_NODE_SIZE
        else:
            G.nodes[node_id]["size"] = scale_size(
                entity_in_degrees[node_id], min_in_degree, max_in_degree
            )

        # HTML hover tooltip
        G.nodes[node_id]["title"] = build_hover_tooltip(node_id, data)

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
        select_menu=True  — node search panel (top-left)
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
        select_menu=True, 
        filter_menu= True #ability to filter nodes and edges based on attributes
    )

    # from_nx translates networkx attributes (title, color, size, label)
    # directly to vis.js node properties - no manual re-mapping needed
    net.from_nx(G)

    # use barnes_hut as physics for KG:
    # gravity pulls unconnected clusters together while edges push aprt
    net.barnes_hut()

    return net


def save_html(net: Network, output_path: str | Path) -> None:
    """Save pyvis Network to a self-contained HTML file a user of the repo can open directly for visual exploration of the KG."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    net.save_graph(str(output_path))
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



