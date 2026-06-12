""" 

config.py
--------- 
Global constants for the kg-dh data collection pipeline.
All API endpoints, authentication, and KG property definitions live here.
Import from this module rather than hardcoding values in other files.
"""

import os
from dotenv import load_dotenv

email = os.environ.get("WIKIDATA_CONTACT_EMAIL", "")

# ── API endpoints ─────────────────────────────────────────────────────────────
URL      = "https://query.wikidata.org/sparql"  # Phase 1: SPARQL endpoint
API_URL  = "https://www.wikidata.org/w/api.php"  # Phase 2: MediaWiki Action API

# Wikimedia requires a descriptive User-Agent with contact info
# https://meta.wikimedia.org/wiki/User-Agent_policy
USER_AGENT = (
    "kg-digital-humanities/0.1.0 "
    f"(https://github.com/FabiLochner/kg-digital-humanities; {email})"
)


# ── KG property definitions ───────────────────────────────────────────────────
# Maps Wikidata property IDs → column names in the authors DataFrame.
# Edit this dict to add or remove properties from the KG.
AUTHOR_PROPS: dict[str, str] = {
    "P27":   "citizenship",
    "P6886": "writing_language",
    "P106":  "occupation",
    "P21":   "sex_gender",
    "P569":  "date_birth",
    "P19":   "place_birth",
    "P570":  "date_death",
    "P69":   "educated_at",
    "P101":  "field_of_work",
    "P136":  "genre",
    "P463":  "member_of",
    "P737":  "influenced_by",
    "P166":  "award_received",
    "P135":  "movement",
}


# Properties whose values are time strings (e.g. '+1883-07-03T00:00:00Z')
# rather than entity QIDs — these need a different extractor in fetch.py.
# All other properties in AUTHOR_PROPS return lists of entity QIDs.
TIME_VALUED_PROPS: set[str] = {"P569", "P570"}  # date_birth, date_death