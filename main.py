#!/usr/bin/env python3
"""Scrape the source repos named in .env and report the listings we haven't seen before."""

import argparse
import json
import os
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


NOTIFY_BATCH_LIMIT = 20
"""Above this many new listings in one run (a cold start, typically), send one summary
notification instead of one per listing — nobody wants 189 buzzes at once."""

# label -> sheet column each person's "interested" button writes to.
INTEREST_BUTTONS = {"Hank interested": "F", "Steve interested": "E"}
INTEREST_VALUE = "Planning to Apply"  # must match the sheet's E/F dropdown option exactly (strict validation)


def approval_actions(listing: Listing) -> list[dict]:
    """Tappable buttons for a listing's notification, one per person. Each POSTs straight to the
    Apps Script web app bound to the sheet (see appscript/Code.gs), which finds the row by apply
    URL and writes INTEREST_VALUE into that person's column — no server of our own to run.
    """
    webhook = os.getenv("APPROVAL_WEBHOOK_URL")
    if not webhook:
        return []

    secret = os.getenv("APPROVAL_WEBHOOK_SECRET")

    def action(label: str, column: str) -> dict:
        body = {"url": listing.url, "column": column, "value": INTEREST_VALUE}
        if secret:
            body["secret"] = secret
        return {
            "action": "http",
            "label": label,
            "url": webhook,
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body),
        }

    return [action(label, column) for label, column in INTEREST_BUTTONS.items()]


def notify_new(new: list[Listing]) -> bool:
    """Notify about new listings. The source data is public, so the notification carries full
    details, not just a count — one push per listing, so tapping it opens that listing's apply
    link directly, with buttons to mark interest without leaving the notification.
    """
    if not new:
        return True

    if len(new) > NOTIFY_BATCH_LIMIT:
        return send(
            f"{len(new)} new internship listings — too many to list individually",
            title="Internship tracker",
            tags="briefcase",
        )

    delivered = True
    for listing in new:
        if not send(
            str(listing),
            title="Internship tracker",
            tags="briefcase",
            actions=approval_actions(listing),
        ):
            delivered = False
    return delivered


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

    for listing in new:
        print(listing, end="\n\n")
    print(f"{len(new)} new of {len(listings)} listings ({len(seen)} seen before)")

    # Save before notifying: a listing already recorded as seen won't be announced twice, even if
    # the push fails.
    save_seen(seen | {listing.url for listing in new if listing.url})

    failed = failed or not notify_new(new)

    env = sheet_env()
    if env:
        write_listings(new, *env)  # TODO: swap in the real approval list once the phone flow lands

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
