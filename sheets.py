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


def _row(listing: Listing) -> list[str]:
    return [
        listing.company,
        listing.role,
        " | ".join(listing.locations),
        listing.url or "",
    ]


def _open_worksheet(sheet_id: str, credentials_file: str):
    client = gspread.service_account(filename=credentials_file)
    return client.open_by_key(sheet_id).sheet1


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


def clear_sheet(sheet_id: str, credentials_file: str) -> None:
    """Clear every data row below the header in columns A-D. Leaves E, F, and row 13 alone."""
    worksheet = _open_worksheet(sheet_id, credentials_file)
    last_row = _last_data_row(worksheet)
    if last_row < DATA_START_ROW:
        return
    worksheet.batch_clear([f"A{DATA_START_ROW}:{DATA_COLUMNS}{last_row}"])
