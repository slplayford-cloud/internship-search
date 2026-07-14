#!/usr/bin/env python3
"""Scrape the source repos named in .env and report the listings we haven't seen before."""

import argparse
import os
import re
import sys

import requests
from dotenv import load_dotenv

from models import Listing
from notify import send
from scrapers import Scraper, SpeedyApplyScraper, Summer2027Scraper
from sheets import clear_sheet, write_listings
from store import load_seen, new_listings, save_seen

SOURCES: dict[str, type[Scraper]] = {
    "SUMMER2027_URL": Summer2027Scraper,
    "SPEEDYAPPLY_URL": SpeedyApplyScraper,
}


def configured_scrapers() -> list[Scraper]:
    scrapers = [
        scraper_class(url)
        for env_var, scraper_class in SOURCES.items()
        if (url := os.getenv(env_var))
    ]
    if not scrapers:
        raise LookupError(f"set at least one of {', '.join(SOURCES)} in the environment or .env")
    return scrapers


RAW_README = re.compile(r"https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/")


def repo_page(url: str) -> str:
    """The repo page behind a raw README URL — tapping a notification should open that, not
    a screenful of raw Markdown."""
    match = RAW_README.match(url)
    return f"https://github.com/{match[1]}/{match[2]}" if match else url


def scrape_all(scrapers: list[Scraper]) -> tuple[list[Listing], bool]:
    listings: list[Listing] = []
    failed = False

    for scraper in scrapers:
        try:
            listings.extend(scraper.scrape())
        except (requests.RequestException, LookupError) as error:
            # One unreachable or restructured source shouldn't sink the others.
            print(f"{scraper.name}: {error}", file=sys.stderr)
            failed = True

    return listings, failed


def sheet_env() -> tuple[str, str] | None:
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    credentials_file = os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE")
    if not (sheet_id and credentials_file):
        print("GOOGLE_SHEET_ID / GOOGLE_SHEETS_CREDENTIALS_FILE not set", file=sys.stderr)
        return None
    return sheet_id, credentials_file


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--clear-sheet",
        action="store_true",
        help="clear tracked listings from the sheet (rows below the header) and exit",
    )
    args = parser.parse_args()

    if args.clear_sheet:
        env = sheet_env()
        if not env:
            return 1
        clear_sheet(*env)
        print("Cleared sheet data rows.")
        return 0

    try:
        scrapers = configured_scrapers()
    except LookupError as error:
        print(error, file=sys.stderr)
        return 1

    listings, failed = scrape_all(scrapers)

    seen = load_seen()
    new = new_listings(listings, seen)

    #send to phone
    #approval comes in
    approved = new  # TODO: swap in the real approval list once the phone flow lands

    env = sheet_env()
    if env:
        write_listings(approved, *env)

    for listing in new:
        print(listing, end="\n\n")
    print(f"{len(new)} new of {len(listings)} listings ({len(seen)} seen before)")

    # Save before notifying: a listing already recorded as seen won't be announced twice, even if
    # the push fails. Only the count goes out — see notify.py on why the body stays contentless.
    save_seen(seen | {listing.url for listing in new if listing.url})

    plural = "s" if len(new) > 1 else ""
    delivered = send(
        f"{len(new)} new internship listing{plural}",
        title="Internship tracker",
        tags="briefcase",
        click=repo_page(scrapers[0].url),
    )
    failed = failed or not delivered

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
