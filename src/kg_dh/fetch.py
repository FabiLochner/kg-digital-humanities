"""
fetch.py
--------
Data collection functions for the two-phase Wikidata extraction pipeline.

Source for the architecture idea: https://gist.github.com/ArloDune/117ee69e72c1ceaae1c45818e5d646fa

Phase 1 — fetch_author_qids_paged():
    Lean SPARQL query returning only QIDs. No OPTIONALs, no label service.
    Uses query templates from queries/authors.py.

Phase 2 — fetch_all_entities():
    wbgetentities API to fetch all author properties per QID.
    Runs on a separate CDN-cached quota from SPARQL.

Phase 3 — resolve_labels():
    Resolves all claim QIDs found in Phase 2 to English labels.
    Also uses wbgetentities — must run after Phase 2.


""" 

import datetime
import time
from email.utils import parsedate_to_datetime

import pandas as pd
import requests

# import constants from config instead of hardcoding
from kg_dh.config import API_URL, AUTHOR_PROPS, TIME_VALUED_PROPS, URL, USER_AGENT
# import query templates from queries
from kg_dh.queries import AUTHOR_QUERIES



### 1) retry helper 

def parse_retry_after(header_val: str | None, default: float = 60.0) -> float:
    """Parse Retry-After header — handles both integer seconds and HTTP-date. Wikidata has 60 seconds query runtime limit.
    https://www.mediawiki.org/wiki/Wikidata_Query_Service/User_Manual#Query_limits"""
    if not header_val:
        return default
    try:
        return max(0.0, float(header_val))
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(header_val)
        return max(0.0, (dt - datetime.datetime.now(datetime.timezone.utc)).total_seconds())
    except Exception:
        return default


### 2) SPARQL helpers (used in Phase 1)


def fetch_sparql(query: str) -> requests.Response:
    """Send a SPARQL SELECT query to WDQS, return raw response."""
    return requests.get(
        URL,
        params={"query": query, "format": "json"},
        headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"}
    )


def parse_to_df(resp: requests.Response) -> pd.DataFrame:
    """Convert a SPARQL JSON response to a clean DataFrame (values only)."""
    data = resp.json()
    rows = [
        {var: binding[var]["value"] for var in binding}
        for binding in data["results"]["bindings"]
    ]
    return pd.DataFrame(rows)


def run_query(query: str, debug: bool = False) -> pd.DataFrame:
    """Fetch a SPARQL query and return results as a DataFrame."""
    resp = fetch_sparql(query)
    if debug:
        print(f"Status: {resp.status_code}")
        print(f"Retry-After: {resp.headers.get('Retry-After')}")
        print(f"Body preview:\n{resp.text[:300]}")
    resp.raise_for_status()
    return parse_to_df(resp)


### 3) Phase 1: collect only Wikidate IDs (QIDs) via SPARQL


def fetch_author_qids_paged(
    country: str,           # selects query template from AUTHOR_QUERIES
    limit: int = 500, #limit based on code from source for archicture (see start of python file)
    max_pages: int = 1,
) -> list[str]:
    """
    Lean SPARQL — no OPTIONALs, no label service, QIDs only.
    Looks up the SPARQL template for `country` from AUTHOR_QUERIES.

    max_pages=1  →   500 QIDs (~10s,  test)
    max_pages=4  → 2,000 QIDs (~2min, exploratory)
    max_pages=56 → full German corpus (~28,000 authors)
    """
    if country not in AUTHOR_QUERIES:
        raise ValueError(f"Unknown country '{country}'. "
                         f"Choose from: {list(AUTHOR_QUERIES.keys())}")
    
    all_qids = []
    for page in range(max_pages):
        offset = page * limit
        # KEY CHANGE: use .format() on the template instead of inline f-string
        query = AUTHOR_QUERIES[country].format(limit=limit, offset=offset)

        resp = fetch_sparql(query)

        # respect rate limit: wait exactly as long as the server requests
        if resp.status_code == 429:
            wait = parse_retry_after(resp.headers.get("Retry-After"))
            print(f"429 on page {page + 1} — waiting {wait:.0f}s")
            time.sleep(wait)
            resp = fetch_sparql(query)  # one retry after waiting

        # raise immediately on any other HTTP error (4xx, 5xx)
        resp.raise_for_status()

        # parse response and extract QID from each entity URI
        df = parse_to_df(resp)
        qids = [uri.split("/")[-1] for uri in df["author"].tolist()]
        all_qids.extend(qids)
        print(f"Page {page + 1}/{max_pages}: +{len(qids)} QIDs | total={len(all_qids)}")

        # fewer results than limit means this is the last page
        if len(qids) < limit:
            print("Last page reached.")
            break

        # courtesy sleep between pages to stay within the 60 CPU-s/min budget
        if page < max_pages - 1:
            time.sleep(5)

    return all_qids



### 4) Phase 2: wbgetentities helpers

def extract_time_from_claims(claims: dict, prop_id: str) -> str | None:
    """
    Extract the first valid time string for a given property (e.g. P569 = date of birth).
    Returns ISO-style string like '+1883-07-03T00:00:00Z', or None if not present.
    """
    if prop_id not in claims:
        # property not present on this entity at all
        return None
    for claim in claims[prop_id]:
        if (
            claim.get("rank") != "deprecated"           # skip superseded values
            and claim["mainsnak"].get("snaktype") == "value"  # skip 'somevalue'/'novalue'
            and claim["mainsnak"]["datavalue"]["type"] == "time"  # confirm it's a time value
        ):
            # return the raw time string from the nested value dict
            return claim["mainsnak"]["datavalue"]["value"]["time"]
    return None


def extract_qids_from_claims(claims: dict, prop_id: str) -> list[str]:
    """
    Extract all valid entity QIDs for a given property (e.g. P106 = occupation).
    Returns a list because properties can be multi-valued (e.g. multiple occupations).
    Returns empty list if property is not present or has no valid values.
    """
    if prop_id not in claims:
        # property not present on this entity at all
        return []
    return [
        claim["mainsnak"]["datavalue"]["value"]["id"]  # extract QID e.g. 'Q36180'
        for claim in claims[prop_id]
        if (
            claim.get("rank") != "deprecated"                        # skip superseded values
            and claim["mainsnak"].get("snaktype") == "value"         # skip 'somevalue'/'novalue'
            and claim["mainsnak"]["datavalue"]["type"] == "wikibase-entityid"  # confirm it's an entity ref
        )
    ]

def parse_entities(entities: dict) -> pd.DataFrame:
    """
    Convert raw wbgetentities API response to one row per author.
    Uses the global AUTHOR_PROPS dict to determine which properties to extract.
    TIME_VALUED_PROPS (P569, P570) use extract_time_from_claims.
    All other properties use extract_qids_from_claims → return lists of QIDs.
    """
    rows = []
    for qid, entity in entities.items():
        if "missing" in entity:
            continue
        claims = entity.get("claims", {})
        row = {
            "author":      f"http://www.wikidata.org/entity/{qid}",
            "authorLabel": entity.get("labels", {}).get("en", {}).get("value", qid),
        }
        # uses imported AUTHOR_PROPS instead of global PROPS
        for prop_id, col_name in AUTHOR_PROPS.items():
            if prop_id in TIME_VALUED_PROPS:
                row[col_name] = extract_time_from_claims(claims, prop_id)
            else:
                row[col_name] = extract_qids_from_claims(claims, prop_id)
        rows.append(row)
    return pd.DataFrame(rows)



def fetch_all_entities(qids: list[str], sleep: float = 1.0) -> pd.DataFrame:
    """
    Phase 2 orchestrator: batch QIDs into groups of 50, call wbgetentities
    for each batch, parse results with parse_entities().
    sleep=1.0s between batches is sufficient — wbgetentities runs on a
    separate CDN-cached quota, not the SPARQL 60 CPU-s/min budget.
    """
    if not qids:
        raise ValueError("QIDs list is empty - Phase 1 returned no results")
    # split full QID list into batches of 50 (API maximum per request)
    batches = [qids[i:i + 50] for i in range(0, len(qids), 50)]
    dfs = []

    for i, batch in enumerate(batches):
        resp = requests.get(
            API_URL,
            params={
                "action":    "wbgetentities",
                "ids":       "|".join(batch),  # pipe-separated QIDs e.g. 'Q905|Q34660'
                "props":     "labels|claims",  # only fetch labels and property claims
                "languages": "en",
                "format":    "json",
            },
            headers={"User-Agent": USER_AGENT}
        )

        # respect rate limit: wait exactly as long as the server requests
        if resp.status_code == 429:
            wait = parse_retry_after(resp.headers.get("Retry-After"))
            print(f"429 on batch {i + 1} — waiting {wait:.0f}s")
            time.sleep(wait)
            resp = requests.get(  # one retry after waiting
                API_URL,
                params={
                    "action":    "wbgetentities",
                    "ids":       "|".join(batch),
                    "props":     "labels|claims",
                    "languages": "en",
                    "format":    "json",
                },
                headers={"User-Agent": USER_AGENT}
            )

        # raise immediately on any other HTTP error (4xx, 5xx)
        resp.raise_for_status()

        # parse the batch response into one row per author using PROPS
        dfs.append(parse_entities(resp.json()["entities"]))
        print(f"Batch {i + 1}/{len(batches)} done")

        # courtesy sleep between batches to avoid hammering the API
        time.sleep(sleep)

    # combine all batch DataFrames into one
    return pd.concat(dfs, ignore_index=True)




### 5) Phase 3: label resolution

def resolve_labels(authors_df: pd.DataFrame, sleep: float = 1.0) -> dict[str, str]:
    """
    Collect all unique QIDs from claim columns in authors_df and resolve
    them to English labels via wbgetentities (labels only, no claims).

    Returns dict[QID, label] saved to data/raw/ alongside the raw authors
    file by collect_data.py, e.g. germany_authors_500_labels.json.

    Runs on the same CDN-cached wbgetentities quota as Phase 2.
    sleep=1.0s between batches is sufficient.
    """


    # step 1: collect all unique QIDs from list columns
    list_cols = [
        col for col in authors_df.columns
        if col not in ("author", "authorLabel", "date_birth", "date_death")
    ]
    all_qids: set[str] = set()
    for col in list_cols:
        for cell in authors_df[col].dropna():
            if isinstance(cell, list):
                all_qids.update(cell)  # add each QID from the list

    # step 2: batch QIDs and fetch labels
    qid_list = list(all_qids)
    batches = [qid_list[i:i + 50] for i in range(0, len(qid_list), 50)]
    label_lookup: dict[str, str] = {}

    for i, batch in enumerate(batches):
        resp = requests.get(
            API_URL,
            params={
                "action":    "wbgetentities",
                "ids":       "|".join(batch),
                "props":     "labels",           # labels only — no claims needed
                "languages": "en",
                "format":    "json",
            },
            headers={"User-Agent": USER_AGENT}
        )

        # respect rate limit
        if resp.status_code == 429:
            wait = parse_retry_after(resp.headers.get("Retry-After"))
            print(f"429 on label batch {i + 1} — waiting {wait:.0f}s")
            time.sleep(wait)
            resp = requests.get(
                API_URL,
                params={
                    "action": "wbgetentities", "ids": "|".join(batch),
                    "props": "labels", "languages": "en", "format": "json",
                },
                headers={"User-Agent": USER_AGENT}
            )

        resp.raise_for_status()

        for qid, entity in resp.json()["entities"].items():
            # fall back to QID itself if no English label exists
            label_lookup[qid] = (
                entity.get("labels", {}).get("en", {}).get("value", qid)
            )

        print(f"Label batch {i + 1}/{len(batches)} done")
        time.sleep(sleep)

    return label_lookup



