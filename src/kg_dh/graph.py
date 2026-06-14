""" 
graph.py
---------

KG construction functions. Reads raw JSON + labels JSON saved in data/raw and builds a 
directed heterogeneous networkx DiGraph where:
    - Author nodes carry demographic attributes (node_type = "author", e.g., sex_gender, date_birth etc.)
    - Entity nodes reprsent edge targets, typed by their property name (e.g., field_of_work, genre, member_of, movement )
    - Directed edges connect authors -> entities with a relation attribute

Due to the multiple node types, the network/Garph is heterogeneous.

Full Node attributes (stored on author node, NOT separate nodes):
    - sex_gender, citizenship, writing_language, occupation, date_birth, date_death

Edge types (each becomes a separate entity node + directed edge):
    - place_birth, educated_at, field_of_work, genre, member_of, influenced_by, award_received, movement 


"""

# import libraries
import json 
from collections import Counter 
from pathlib import Path 
import networkx as nx

### 1) property classification 

# stored as author node attributes — not separate graph nodes
NODE_ATTRIBUTE_PROPS: set[str] = {
    "sex_gender",
    "citizenship",
    "writing_language",
    "occupation",
    "date_birth", 
    "date_death"
}

# each becomes a typed entity node + directed edge from author
EDGE_TYPE_PROPS: list[str] = [
    "place_birth",
    "educated_at",
    "field_of_work",
    "genre",
    "member_of",
    "influenced_by",
    "award_received",
    "movement",
]


### 2) data loading

def load_data(
    raw_path: str | Path,
    labels_path: str | Path,
) -> tuple[list[dict], dict[str, str]]:
    """Load raw authors JSON and QID labels lookup JSON from disk."""
    with open(raw_path, encoding="utf-8") as f:
        authors = json.load(f)
    with open(labels_path, encoding="utf-8") as f:
        labels = json.load(f)
    return authors, labels


### 3) QID and label helper functions 

def extract_qid(uri: str) -> str:
    """Extract QID from full Wikidata URI.
    'http://www.wikidata.org/entity/Q1000002' → 'Q1000002'
    """
    return uri.split("/")[-1]


def resolve_label(qid: str, labels: dict[str, str]) -> str:
    """Resolve a single QID to its English label. Falls back to QID if not found."""
    return labels.get(qid, qid)


def resolve_label_list(qids: list[str], labels: dict[str, str]) -> list[str]:
    """Resolve a list of QIDs to their English labels."""
    return [resolve_label(qid, labels) for qid in qids]


def parse_year(date_str: str | None) -> str | None:
    """Extract year from clean date string 'YYYY-MM-DD' → 'YYYY'."""
    if not date_str:
        return None
    # date_birth is already in clean YYYY-MM-DD format from clean_date()
    return date_str[:4]


### 4) graph construction 

def build_graph(
    authors: list[dict],
    labels: dict[str, str],
    edge_types: list[str] | str = "all",
) -> nx.DiGraph:
    """ 
    Build a directed heterogeneous KG from raw author data.

    Parameters
    ----------
    authors    : list of author records loaded from raw JSON
    labels     : QID → English label lookup dict from labels JSON
    edge_types : list of property names to include as edges,
                 or "all" to include all EDGE_TYPE_PROPS


    Returns
    -------
    nx.DiGraph where author nodes have demographic node attributes
    and entity nodes are connected by typed directed edges.

    Node attributes on author nodes:
        label, node_type, sex_gender, citizenship, writing_language,
        occupation, birth_year, death_year

    Node attributes on entity nodes:
        label         — human-readable name (e.g. "National Prize of East Germany")
        node_type     — category of the entity (e.g. "award", "place", "movement")
                        mapped via EDGE_TYPE_TO_NODE_TYPE, not the property name

    Edge attributes:
        relation      — the property name connecting author to entity
                        (e.g. "award_received", "influenced_by")
    
    """

    # resolve which edge types to include
    if edge_types == "all":
        active_edge_types = EDGE_TYPE_PROPS
    else:
        # validate against known types, preserve order
        active_edge_types = [et for et in edge_types if et in EDGE_TYPE_PROPS]
        unknown = [et for et in edge_types if et not in EDGE_TYPE_PROPS]
        if unknown:
            raise ValueError(f"Unknwon edge types: {unknown}."
                             f"Valid options: {EDGE_TYPE_PROPS}")
        

    # initialize directed graph
    G = nx.DiGraph()

    for author in authors:

        # 1) extract QID from URI
        author_qid = extract_qid(author["author"])
        author_label = author.get("authorLabel", author_qid)

        # 2) resolve node attributes
        sex_gender = resolve_label_list(author.get("sex_gender", []), labels)
        citizenship = resolve_label_list(author.get("citizenship", []), labels)
        writing_language = resolve_label_list(author.get("writing_language", []), labels)
        # only keep top 3 occupations to avoid noise in visualization
        occupation     = resolve_label_list(author.get("occupation", [])[:3], labels)   
        birth_year = resolve_label(author.get("date_birth"))
        death_year = resolve_label(author.get("date_death"))

        # 3) add author node
        G.add_node(
            author_qid,
            label = author_label,
            node_type = "author",
            # demographic attributes stored as strings for hover display
            sex_gender = ", ".join(sex_gender) if sex_gender else "n/a",
            citizenship = ", ".join(citizenship) if citizenship else "n/a",
            writing_language = ", ".join(writing_language) if writing_language else "n/a",
            occupation = ", ".join(occupation) if occupation else "n/a",
            birth_year = birth_year or "n/a",
            death_year = death_year or "n/a",
        )     

        # 4) add entity nodes and typed directed edges
        for edge_type in active_edge_types:
            entity_qids = author.get(edge_type, [])

            for entity_qid in entity_qids:
                entity_label = resolve_label(entity_qid, labels)

                # add entity node only on first encounter
                if not G.has_node(entity_qid):
                    G.add_node(
                        entity_qid,
                        label = entity_label,
                        node_type = edge_type, # e.g., "movement", "award received"
                    )

                # create directed edge: author -> entity with typed relation attribute
                G.add_edge(
                    author_qid,
                    entity_qid,
                    relation = edge_type
                )

    return G


### 5) graph filtering (relevant for larger graphs)

def filter_graph(G: nx.DiGraph, min_degree: int = 1) -> nx.DiGraph:
    """ 
    Return a subgraph keeping only nodes with degree >= min_degree.
    Removes entity nodes connected to fewer than min_degree authors,
    reducing visual noise at larger scales.

    Empirically grounded defaults by scale (German author corpus):
        100 authors -> min_degree = 1
        1.000 authors -> min_degree = 2
        3.000 authors -> degree filtering alone will be insufficient; should be combined with
                            edge-type filtering in scripts/build_kg() first
    
    """
    nodes_to_keep = [n for n, d in G.degree() if d >= min_degree]
    return G.subgraph(nodes_to_keep).copy()




