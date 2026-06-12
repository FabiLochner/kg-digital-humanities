""" 
authors.py
----------
SPARQL query templates for Phase 1 author QID collection, one per country.
Queries are stored as format strings — {limit} and {offset} are filled
in by fetch_author_qids_paged() in fetch.py at runtime.

Wikidata QIDs used:
    Q5      = human
    Q36180  = writer
    Q6625963= novelist
    Q49757  = poet
    Q183    = Germany
    Q188    = German language    
    Q145    = United Kingdom
    Q29999  = Kingdom of the Netherlands
    Q7411   = Dutch language
"""

# ── SPARQL query templates per country ───────────────────────────────────────
# Each query selects DISTINCT author QIDs only — no OPTIONALs, no label
# service — to minimise SPARQL CPU cost in Phase 1.
# {limit} and {offset} are filled in at runtime via .format().

AUTHOR_QUERIES: dict[str, str] = {

    "germany": """
        SELECT DISTINCT ?author WHERE {{ # remove duplicate authors
            ?author wdt:P31 wd:Q5. # humans
            # German citizenship OR writes in German language
            {{ ?author wdt:P27 wd:Q183. }} UNION    # citizenship - Germany
            {{ ?author wdt:P6886 wd:Q188. }}         # language written - German
            # occupation: writer OR novelist OR poet
            {{ ?author wdt:P106 wd:Q36180. }} UNION  # occupation - writer
            {{ ?author wdt:P106 wd:Q6625963. }} UNION # occupation - novelist
            {{ ?author wdt:P106 wd:Q49757. }}         # occupation - poet
            }}
            ORDER BY ?author
            LIMIT {limit}
            OFFSET {offset}
            """,

    "uk": """ 
        SELECT DISTINCT ?author WHERE {{
          ?author wdt:P31 wd:Q5. # humans
          # UK citizenship only (no writing language condition for UK)
          ?author wdt:P27 wd:Q145.             # citizenship - United Kingdom
          # occupation: writer OR novelist OR poet
          {{ ?author wdt:P106 wd:Q36180. }} UNION  # occupation - writer
          {{ ?author wdt:P106 wd:Q6625963. }} UNION # occupation - novelist
          {{ ?author wdt:P106 wd:Q49757. }}         # occupation - poet
        }}
        ORDER BY ?author
        LIMIT {limit}
        OFFSET {offset}
    

        """,

    "netherlands": """
        SELECT DISTINCT ?author WHERE {{
          ?author wdt:P31 wd:Q5. # humans
          # Dutch citizenship OR writes in Dutch language
          {{ ?author wdt:P27 wd:Q29999. }} UNION     # citizenship - Kingdom of Netherlands
          {{ ?author wdt:P6886 wd:Q7411. }}        # language written - Dutch
          # occupation: writer OR novelist OR poet
          {{ ?author wdt:P106 wd:Q36180. }} UNION  # occupation - writer
          {{ ?author wdt:P106 wd:Q6625963. }} UNION # occupation - novelist
          {{ ?author wdt:P106 wd:Q49757. }}         # occupation - poet
        }}
        ORDER BY ?author
        LIMIT {limit}
        OFFSET {offset}


        """,

}

# ── Approximate author counts per country ────────────────────────────────────
# Used to calculate max_pages for --all in collect_data.py.
# These are estimates — verify by running the estimate query on
# https://query.wikidata.org before a full corpus run.
# Estimate query: same WHERE clause above but SELECT ?author ?itemLabel
# without DISTINCT LIMIT/OFFSET, to get the raw count.
MAX_AUTHORS: dict[str, int] = {
    "germany":     28_000,  # verified ~27,273 distinct authors as of 2025-06-12
    "uk":          None,    # query returns error 
    "netherlands": 7000,    # verified ~6.918 distinct authors as of 2025-06-12
}