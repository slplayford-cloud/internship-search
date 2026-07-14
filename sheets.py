"""Writes approved listings to the Google Sheet that tracks our internship pipeline.

Sheet layout: headers live in row 13 (A=Company, B=Position, C=Location, D=Link,
E=Age), data starts row 14. Age is days-since-posted as a plain number — never the
source's raw "Jul 07" / "12d" text — so the sheet sorts by it. Columns F (Stephen)
and G (Henry) are owned by the approval flow and are only rewritten wholesale,
never given values of our own.
"""

import re
from datetime import date, datetime

import gspread

from models import Listing

HEADER_ROW = 13
DATA_START_ROW = HEADER_ROW + 1
DATA_COLUMNS = "E"  # A through E: Company, Position, Location, Link, Age
INTEREST_COLUMNS = "G"  # F and G, one per person; written by the approval flow, not by us
DISCARD_TAB = "Discarded"
"""Rows disposed of — by the phone "Not interested" button or by prune_uninterested — are moved
here rather than deleted, so a mistake is recoverable. Same tab name as in appscript/Code.gs."""


AGE_RELATIVE = re.compile(r"^(\d+)\s*(mo|[hdwm])$", re.IGNORECASE)
AGE_UNIT_DAYS = {"m": 0, "h": 0, "d": 1, "w": 7, "mo": 30}


def age_days(posted: str, today: date | None = None) -> int | None:
    """How many days ago a listing was posted, from either style the sources use.

    Handles relative ages ("12d", and defensively "5h" / "2w" / "3mo") and month-day dates
    ("Jul 07", taken as the most recent one not in the future). None when unparseable.
    """
    posted = (posted or "").strip()
    today = today or date.today()

    if match := AGE_RELATIVE.match(posted):
        count, unit = match.groups()
        return int(count) * AGE_UNIT_DAYS[unit.lower()]

    try:
        parsed = datetime.strptime(posted, "%b %d")
        posted_date = date(today.year, parsed.month, parsed.day)
        if posted_date > today:
            posted_date = date(today.year - 1, parsed.month, parsed.day)
    except ValueError:
        return None
    return (today - posted_date).days


def _row(listing: Listing) -> list[str | int]:
    age = age_days(listing.posted)
    return [
        listing.company,
        listing.role,
        " | ".join(listing.locations),
        listing.url or "",
        age if age is not None else "",
    ]


def _open_spreadsheet(sheet_id: str, credentials_file: str):
    client = gspread.service_account(filename=credentials_file)
    return client.open_by_key(sheet_id)


def _open_worksheet(sheet_id: str, credentials_file: str):
    return _open_spreadsheet(sheet_id, credentials_file).sheet1


def _last_data_row(worksheet) -> int:
    """The last row with data in A:E, or HEADER_ROW if there is none."""
    values = worksheet.get_values(f"A{DATA_START_ROW}:A")
    return DATA_START_ROW + len(values) - 1 if values else HEADER_ROW


def write_listings(listings: list[Listing], sheet_id: str, credentials_file: str) -> None:
    """Write each listing as a row in A-D, starting right after the last filled row."""
    if not listings:
        return

    worksheet = _open_worksheet(sheet_id, credentials_file)
    next_row = _last_data_row(worksheet) + 1
    worksheet.update(f"A{next_row}", [_row(listing) for listing in listings])


NOT_INTERESTED_VALUE = "Not Planning to Apply"
"""Must match the E/F dropdown option exactly — the sheet's validation is strict."""


def _uninterested(status: str) -> bool:
    """A status cell that counts as "this person doesn't want it": empty, or explicitly marked."""
    return not status.strip() or status.strip().lower() == NOT_INTERESTED_VALUE.lower()


def prune_uninterested(sheet_id: str, credentials_file: str) -> int:
    """Move every data row where nobody marked interest in F or G to the Discarded tab.

    On-demand disposal: run it once new rows have been triaged, and any row where both statuses
    are blank or "Not Planning to Apply" is archived, leaving the tracker tab holding only
    listings someone is acting on. On the rows that stay, a blank status means that person passed,
    so it's made explicit: it's set to "Not Planning to Apply" rather than left unselected.
    Returns how many rows were moved.
    """
    spreadsheet = _open_spreadsheet(sheet_id, credentials_file)
    worksheet = spreadsheet.sheet1
    last_row = _last_data_row(worksheet)
    if last_row < DATA_START_ROW:
        return 0

    width = ord(INTEREST_COLUMNS) - ord("A") + 1
    data_width = ord(DATA_COLUMNS) - ord("A") + 1
    rows = worksheet.get_values(f"A{DATA_START_ROW}:{INTEREST_COLUMNS}{last_row}")

    keep: list[list[str | int]] = []
    discard: list[list[str | int]] = []
    filled_blanks = False
    for row in rows:
        row = row + [""] * (width - len(row))
        # get_values reads the numeric Age cell back as a string; rewriting it as one would turn
        # the cell into text and break sorting, so restore the number.
        age = row[data_width - 1]
        row[data_width - 1] = int(age) if age.strip().isdigit() else age
        statuses = row[data_width:width]
        if all(_uninterested(status) for status in statuses):
            discard.append(row[:data_width])
        else:
            filled_blanks = filled_blanks or any(not status.strip() for status in statuses)
            keep.append(
                row[:data_width]
                + [status if status.strip() else NOT_INTERESTED_VALUE for status in statuses]
            )

    if not discard and not filled_blanks:
        return 0

    if discard:
        _discard_tab(spreadsheet).append_rows(discard)

    # Rewrite the block in place: clear it, then put the kept rows (E/F included) back on top.
    worksheet.batch_clear([f"A{DATA_START_ROW}:{INTEREST_COLUMNS}{last_row}"])
    if keep:
        worksheet.update(f"A{DATA_START_ROW}", keep)

    return len(discard)


def _discard_tab(spreadsheet):
    try:
        return spreadsheet.worksheet(DISCARD_TAB)
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(DISCARD_TAB, rows=1, cols=7)


def clear_sheet(sheet_id: str, credentials_file: str) -> None:
    """Clear every data row below the header in columns A-E. Leaves F, G, and row 13 alone."""
    worksheet = _open_worksheet(sheet_id, credentials_file)
    last_row = _last_data_row(worksheet)
    if last_row < DATA_START_ROW:
        return
    worksheet.batch_clear([f"A{DATA_START_ROW}:{DATA_COLUMNS}{last_row}"])
