"""Writes approved listings to the Google Sheet that tracks our internship pipeline.

Sheet layout: headers live in row 13 (A=Company, B=Position, C=Location, D=Link),
data starts row 14. Columns E and F are owned by the approval flow and are never
touched here.
"""

import gspread

from models import Listing

HEADER_ROW = 13
DATA_START_ROW = HEADER_ROW + 1
DATA_COLUMNS = "D"  # A through D
INTEREST_COLUMNS = "F"  # E and F, one per person; written by the approval flow, not by us
DISCARD_TAB = "Discarded"
"""Rows disposed of — by the phone "Not interested" button or by prune_uninterested — are moved
here rather than deleted, so a mistake is recoverable. Same tab name as in appscript/Code.gs."""


def _row(listing: Listing) -> list[str]:
    return [
        listing.company,
        listing.role,
        " | ".join(listing.locations),
        listing.url or "",
    ]


def _open_spreadsheet(sheet_id: str, credentials_file: str):
    client = gspread.service_account(filename=credentials_file)
    return client.open_by_key(sheet_id)


def _open_worksheet(sheet_id: str, credentials_file: str):
    return _open_spreadsheet(sheet_id, credentials_file).sheet1


def _last_data_row(worksheet) -> int:
    """The last row with data in A:D, or HEADER_ROW if there is none."""
    values = worksheet.get_values(f"A{DATA_START_ROW}:A")
    return DATA_START_ROW + len(values) - 1 if values else HEADER_ROW


def write_listings(listings: list[Listing], sheet_id: str, credentials_file: str) -> None:
    """Write each listing as a row in A-D, starting right after the last filled row."""
    if not listings:
        return

    worksheet = _open_worksheet(sheet_id, credentials_file)
    next_row = _last_data_row(worksheet) + 1
    worksheet.update(f"A{next_row}", [_row(listing) for listing in listings])


def _uninterested(status: str) -> bool:
    """A status cell that counts as "nobody wants this": empty, or explicitly marked."""
    return not status.strip() or status.strip().lower() == "not interested"


def prune_uninterested(sheet_id: str, credentials_file: str) -> int:
    """Move every data row with no interest marked in E or F to the Discarded tab.

    On-demand disposal: run it once new rows have been triaged, and anything nobody marked (or
    that someone marked "not interested" by hand) is archived, leaving the tracker tab holding
    only listings someone is acting on. Returns how many rows were moved.
    """
    spreadsheet = _open_spreadsheet(sheet_id, credentials_file)
    worksheet = spreadsheet.sheet1
    last_row = _last_data_row(worksheet)
    if last_row < DATA_START_ROW:
        return 0

    width = ord(INTEREST_COLUMNS) - ord("A") + 1
    rows = worksheet.get_values(f"A{DATA_START_ROW}:{INTEREST_COLUMNS}{last_row}")
    padded = [row + [""] * (width - len(row)) for row in rows]

    keep = [row for row in padded if not all(_uninterested(status) for status in row[4:width])]
    discard = [row for row in padded if all(_uninterested(status) for status in row[4:width])]
    if not discard:
        return 0

    _discard_tab(spreadsheet).append_rows([row[: ord(DATA_COLUMNS) - ord("A") + 1] for row in discard])

    # Rewrite the block in place: clear it, then put the kept rows (E/F included) back on top.
    worksheet.batch_clear([f"A{DATA_START_ROW}:{INTEREST_COLUMNS}{last_row}"])
    if keep:
        worksheet.update(f"A{DATA_START_ROW}", keep)

    return len(discard)


def _discard_tab(spreadsheet):
    try:
        return spreadsheet.worksheet(DISCARD_TAB)
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(DISCARD_TAB, rows=1, cols=6)


def clear_sheet(sheet_id: str, credentials_file: str) -> None:
    """Clear every data row below the header in columns A-D. Leaves E, F, and row 13 alone."""
    worksheet = _open_worksheet(sheet_id, credentials_file)
    last_row = _last_data_row(worksheet)
    if last_row < DATA_START_ROW:
        return
    worksheet.batch_clear([f"A{DATA_START_ROW}:{DATA_COLUMNS}{last_row}"])
