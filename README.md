# Knowledge Graph for Digital Humanities

![KG.png](docs%2F/germany_authors_3000_2026-06-12_kg_all_html.png)


> A reproducible pipeline for constructing and interactively visualizing heterogeneous Knowledge Graphs (KGs) of German, UK and Dutch language literary authors from Wikidata — built for exploratory research in Digital Humanities.

---

## Table of Contents

1. [Project Description](#project-description)
2. [KG Visualization Preview](#kg-visualization-preview)
3. [Project Structure](#project-structure)
4. [Installation](#installation)
5. [Pipeline Overview](#pipeline-overview)
6. [Usage](#usage)
   - [Step 1 — Data Collection](#step-1--data-collection)
   - [Step 2 — KG Construction & Visualization](#step-2--kg-construction--visualization)
7. [KG Design Decisions](#kg-design-decisions)
8. [Visualization Features](#visualization-features)
9. [Scaling Guide](#scaling-guide)
10. [Data Sources & Acknowledgements](#data-sources--acknowledgements)
11. [License](#license)

---

## Project Description

This project builds a **directed, heterogeneous Knowledge Graph** of literary authors from [Wikidata](https://www.wikidata.org/), with a focus on German, UK and Dutch language writers (novelists, poets, and writers etc.). The pipeline is designed to be fully reproducible, configurable by country and author count, and easy to explore via self-contained interactive HTML files and GEXF files to be explored in tools such as [Gephi](https://gephi.org/).

**What it does:**

- Queries Wikidata for authors matching configurable criteria (country, language, occupation)
- Collects biographical and literary properties for each author (awards, movements, education, influences, etc.)
- Constructs a heterogeneous NetworkX DiGraph with author nodes and typed entity nodes
- Visualizes the KG as an interactive HTML file (pyvis) or exports to GEXF for Gephi

**Why it was built:**

Literary history is rich with connections between authors, movements, institutions and influences that are not easily visible in tabular data. A KG representation makes these relational patterns explorable — who influenced whom, which movements connect authors, which awards cluster certain writers, which universities produced literary figures etc.

**Technologies used:**

| Tool | Purpose |
|---|---|
| Python 3.14 + uv | Runtime and package management |
| Wikidata SPARQL API | Phase 1: collecting author QIDs |
| Wikidata `wbgetentities` API | Phase 2: fetching author properties |
| NetworkX | KG graph construction and statistics |
| pyvis | Interactive HTML visualization (≤ 3,000 nodes) |
| Gephi (GEXF export) | Visualization for 3,000+ authors |

---

## KG Visualization Preview

The interactive HTML visualizations and GEXF files are available in `results/graphs/`. Open the HTML files directly in any browser — no server or internet connection needed. Export the GEXF files to Gephi to explore them. 

| Scale | File | Description |
|---|---|---|
| 100 authors | [`results/graphs/germany_authors_100_2026-06-12_kg_all.html`](results/graphs/germany_authors_100_2026-06-12_kg_all.html) | Full KG, all edge types |
| 1,000 authors | [`results/graphs/germany_authors_1000_2026-06-12_kg_all.html`](results/graphs/germany_authors_1000_2026-06-12_kg_all.html) | Full KG, all edge types |
| 3,000 authors | [`results/graphs/germany_authors_3000_2026-06-12_kg_all.html`](results/graphs/germany_authors_3000_2026-06-12_kg_all.html) | Full KG, all edge types |
| 3,000 authors | [`results/graphs/germany_authors_3000_2026-06-12_kg_all.gexf`](results/graphs/germany_authors_3000_2026-06-12_kg_all.gexf) | Full KG, all edge types |

*Node colours represent entity types (see legend in the HTML). Node sizes for entity nodes reflect how many authors connect to them (in-degree). Author nodes are uniform in size. The bottom-right panel shows the top 5 most-connected entities per type.*


---

## Project Structure

```
kg-digital-humanities/
│
├── data/
│   └── raw/                        # Collected author data (JSON)
│       ├── germany_authors_100_raw_2026-06-12.json
│       ├── germany_authors_100_labels_2026-06-12.json
│       ├── germany_authors_1000_raw_2026-06-12.json
│       ├── germany_authors_1000_labels_2026-06-12.json
│       └── ...
│
├── docs/                           # Documentation assets (e.g. screenshots)
│
├── notebooks/
│   └── tutorials/
│       └── wdqs_sparqlwrapper_test.ipynb   # Wikidata API exploration notebook
│
├── results/
│   └── graphs/                     # KG visualizations
│       ├── germany_authors_100_2026-06-12_kg_all.html
│       └── germany_authors_1000_2026-06-12_kg_all.html
│       └── ...
│
├── scripts/
│   ├── collect_data.py             # CLI: collect author data from Wikidata
│   └── build_kg.py                 # CLI: build and visualize the KG
│
├── src/kg_dh/
│   ├── config.py                   # API endpoints, USER_AGENT, AUTHOR_PROPS
│   ├── fetch.py                    # Phase 1 + Phase 2 + Phase 3 data collection
│   ├── graph.py                    # KG construction (NetworkX DiGraph)
│   ├── visualize.py                # pyvis rendering + Gephi GEXF export
│   └── queries/
│       ├── __init__.py
│       └── authors.py              # SPARQL query templates per country
│
├── tests/                          # Unit tests (to be expanded)
├── .gitignore
├── .python-version
├── CITATION.cff
├── LICENSE
├── README.md
├── pyproject.toml
└── uv.lock
```

---

## Installation

### Prerequisites

- [Python 3.14+](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (package manager)

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/FabiLochner/kg-digital-humanities.git
cd kg-digital-humanities

# 2. Install dependencies
uv sync

# 3. Set up your Wikidata User-Agent (required by Wikimedia policy)
cp .env.example .env
# Edit .env and add your contact email:
# WIKIDATA_CONTACT_EMAIL=your-email@example.com
```

> **Why a User-Agent?** Wikimedia requires all automated clients to identify themselves with a contact email. See the [Wikimedia User-Agent policy](https://meta.wikimedia.org/wiki/User-Agent_policy).

---

## Pipeline Overview

The data collection follows a **two-phase architecture** to avoid hitting Wikidata SPARQL rate limits (60 CPU-seconds/minute):

```
Phase 1 — SPARQL (lean, QIDs only)
    ↓  Wikidata Query Service
    [author QIDs]

Phase 2 — wbgetentities API (CDN-cached, separate quota)
    ↓  MediaWiki Action API — batches of 50 QIDs
    [author properties as QID lists]
    [English labels for all QIDs]

Phase 3 — Label resolution (same API, same batch size)
    ↓  wbgetentities — labels only
    [QID → label lookup dict]

    ↓  save to data/raw/

KG Construction — NetworkX DiGraph
    ↓  src/kg_dh/graph.py
    [heterogeneous directed graph]

Visualization — pyvis HTML or Gephi GEXF
    ↓  src/kg_dh/visualize.py
    [results/graphs/*.html  or  *.gexf]
```

Architecture inspired by [this approach](https://gist.github.com/ArloDune/117ee69e72c1ceaae1c45818e5d646fa).

---

## Usage

All commands are run from the **project root** using `uv run`.

### Step 1 — Data Collection

Collects author data from Wikidata and saves two JSON files to `data/raw/`.

```bash
# 100 German authors (~30 seconds)
uv run scripts/collect_data.py --country germany --limit 100 --max-pages 1

# 1,000 German authors (~2 minutes)
uv run scripts/collect_data.py --country germany --limit 500 --max-pages 2

# 10,000 German authors (~12 minutes)
uv run scripts/collect_data.py --country germany --limit 500 --max-pages 20

# Full German corpus (~28,000 authors, ~35 minutes)
# On Mac, prevent sleep during long runs:
caffeinate -i uv run scripts/collect_data.py --country germany --all
```

**Output files:**

```
data/raw/germany_authors_100_raw_2026-06-12.json    # author records with QIDs
data/raw/germany_authors_100_labels_2026-06-12.json # QID → label lookup
```

**Available countries:**

| `--country` | Condition |
|---|---|
| `germany` | German citizenship OR writes in German |
| `uk` | UK citizenship |
| `netherlands` | Dutch citizenship OR writes in Dutch |

---

### Step 2 — KG Construction & Visualization

Builds the Knowledge Graph from collected data and saves an interactive HTML or GEXF file.

```bash
# e.g., 100 authors, all edge types → HTML (recommended for 1st exploration)
uv run scripts/build_kg.py \
    --input data/raw/germany_authors_100_raw_2026-06-12.json \
    --labels data/raw/germany_authors_100_labels_2026-06-12.json \
    --edge-types all \
    --output-format html

# e.g., 1.000 authors, all edge types → HTML (recommended for 2nd exploration; reveals more patterns)
uv run scripts/build_kg.py \
    --input data/raw/germany_authors_100_raw_2026-06-12.json \
    --labels data/raw/germany_authors_100_labels_2026-06-12.json \
    --edge-types influenced_by,movement,member_of,field_of_work \
    --output-format html

# e.g., 3,000 authors, filtered edges, remove low-degree nodes → HTML
uv run scripts/build_kg.py \
    --input data/raw/germany_authors_3000_raw_2026-06-12.json \
    --labels data/raw/germany_authors_3000_labels_2026-06-12.json \
    --edge-types influenced_by,movement,member_of \
    --min-degree 2 \
    --output-format html

# e.g., 10,000+ authors → Gephi GEXF export
uv run scripts/build_kg.py \
    --input data/raw/germany_authors_10000_raw_2026-06-12.json \
    --labels data/raw/germany_authors_10000_labels_2026-06-12.json \
    --edge-types all \
    --output-format gexf
```

**Output files:**

```
results/graphs/germany_authors_100_2026-06-12_kg_all.html
```

Open the HTML file directly in your browser — no server needed.

---

## KG Design Decisions

The KG is a **directed heterogeneous graph** with two node categories:

### Author nodes (uniform size, blue)

Each author is one node. Properties stored as node attributes (not separate graph nodes):

| Attribute | Wikidata property |
|---|---|
| `sex_gender` | P21 |
| `citizenship` | P27 |
| `writing_language` | P6886 |
| `occupation` | P106 (top 3) |
| `birth_year` | P569 |
| `death_year` | P570 |

### Entity nodes (sized by in-degree)

Each unique value becomes a node connected to authors by a typed directed edge:

| Edge type | Entity node | Wikidata property |
|---|---|---|
| `place_birth` | city/region | P19 |
| `educated_at` | institution | P69 |
| `field_of_work` | field | P101 |
| `genre` | literary genre | P136 |
| `member_of` | organisation/academy | P463 |
| `influenced_by` | person | P737 |
| `award_received` | award | P166 |
| `movement` | literary movement | P135 |

Entity node size scales with **in-degree** (number of authors connected to it) — making high-connectivity hubs like Berlin, Leipzig University, or the Cross of the Order of Merit visually prominent.

---

## Visualization Features

The interactive HTML files include:

| Feature | Description |
|---|---|
| **Hover tooltips** | Author nodes show sex/gender, citizenship, birth/death year, occupation. Entity nodes show type and label. |
| **Node colours** | Each entity type has a distinct colour (see legend panel in the HTML) |
| **Colour legend** | Fixed panel (bottom-left) mapping colours to node types |
| **Top-5 stats panel** | Fixed panel (bottom-right) showing the entities with highest in-degree per type |
| **Filter panel** | Top bar — filter nodes by `node_type`, citizenship, and other attributes |
| **Physics** | Barnes-Hut force-directed layout with interactive dragging |
| **Gephi export** | GEXF files for Gephi analysis at 30,000+ author scale |

---


## Data Sources & Acknowledgements

- **Wikidata** — Knowledge base maintained by the Wikimedia Foundation. Data available under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).
- **Two-phase extraction architecture** — inspired by [this GitHub Gist](https://gist.github.com/ArloDune/117ee69e72c1ceaae1c45818e5d646fa).
- **Project structure** follows the [Good Research Code](https://goodresearch.dev/setup) guidelines.
- **Conventional Commits** used for all commit messages, following [this guide](https://www.freecodecamp.org/news/how-to-write-better-git-commit-messages/).

---

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

---

