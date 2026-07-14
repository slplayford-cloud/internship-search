"""Tracks which listings we've already seen, keyed by their apply URL."""

from pathlib import Path

from models import Listing

SEEN_FILE = Path("seen_urls.txt")


def load_seen(path: Path = SEEN_FILE) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text().splitlines() if line.strip()}


def save_seen(urls: set[str], path: Path = SEEN_FILE) -> None:
    path.write_text("\n".join(sorted(urls)) + "\n")


def new_listings(listings: list[Listing], seen: set[str]) -> list[Listing]:
    """The listings whose apply URL we haven't seen before, one per URL.

    A closed listing has no URL, so there's nothing unique to track it by, and it's skipped.
    """
    new: list[Listing] = []
    urls = set(seen)

    for listing in listings:
        if listing.url and listing.url not in urls:
            urls.add(listing.url)
            new.append(listing)

    return new
