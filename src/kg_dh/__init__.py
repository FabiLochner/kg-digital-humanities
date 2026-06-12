"""
kg_dh
-----
Public API for the kg-digital-humanities data collection pipeline.
Import from here rather than from submodules directly.
"""

from kg_dh.config import AUTHOR_PROPS, TIME_VALUED_PROPS
from kg_dh.queries import AUTHOR_QUERIES, MAX_AUTHORS
from kg_dh.fetch import (
    fetch_author_qids_paged,
    fetch_all_entities,
    resolve_labels,
)

__all__ = [
    "AUTHOR_PROPS",
    "TIME_VALUED_PROPS",
    "AUTHOR_QUERIES",
    "MAX_AUTHORS",
    "fetch_author_qids_paged",
    "fetch_all_entities",
    "resolve_labels",
]