"""Tracks which listings we've already seen, keyed by their apply URL.

The same job is often listed by more than one source with a cosmetically different URL — one
repo appends `?utm_source=...` to every link, and Greenhouse jobs show up under both
`boards.greenhouse.io` and `job-boards.greenhouse.io`. So URLs are canonicalized before being
compared or stored, and a listing counts as seen if its *canonical* URL is.
"""

from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from models import Listing

SEEN_FILE = Path("seen_urls.txt")

TRACKING_PREFIXES = ("utm_",)
"""Query params that only say where a link was found, never which job it points at. Job-board
params like gh_jid, jr_id, or token DO identify the job and must survive canonicalization."""

HOST_ALIASES = {"job-boards.greenhouse.io": "boards.greenhouse.io"}
"""Hostnames that serve the same jobs under different names."""


def canonical_url(url: str) -> str:
    """The dedup key for an apply URL: the URL minus everything that varies by source.

    Drops tracking params (utm_*), the fragment, and a trailing slash; lowercases the host and
    collapses known host aliases. Everything else — including job-identifying query params — is
    kept, so distinct jobs never collapse into one.
    """
    parts = urlsplit(url.strip())
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    host = HOST_ALIASES.get(host, host)
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if not key.lower().startswith(TRACKING_PREFIXES)
        ]
    )
    return urlunsplit((parts.scheme.lower(), host, parts.path.rstrip("/"), query, ""))


def load_seen(path: Path = SEEN_FILE) -> set[str]:
    """The canonical URLs seen so far. Lines written before canonicalization existed are
    canonicalized (and thereby de-duplicated) on the way in."""
    if not path.exists():
        return set()
    return {canonical_url(line) for line in path.read_text().splitlines() if line.strip()}


def save_seen(urls: set[str], path: Path = SEEN_FILE) -> None:
    path.write_text("\n".join(sorted(canonical_url(url) for url in urls)) + "\n")


def new_listings(listings: list[Listing], seen: set[str]) -> list[Listing]:
    """The listings whose apply URL we haven't seen before, one per canonical URL.

    A closed listing has no URL, so there's nothing unique to track it by, and it's skipped.
    """
    new: list[Listing] = []
    urls = set(seen)

    for listing in listings:
        if not listing.url:
            continue
        key = canonical_url(listing.url)
        if key not in urls:
            urls.add(key)
            new.append(listing)

    return new
