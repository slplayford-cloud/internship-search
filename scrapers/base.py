"""Fetching and Markdown helpers shared by the per-source scrapers.

Each source is a GitHub repo whose README keeps its listings in Markdown tables, and we read that
raw Markdown rather than the rendered repo page — the table *is* the data, so it survives GitHub
restyling its HTML. Cells still carry inline HTML (the Apply <a>, <br>-separated locations), so
those get handed to BeautifulSoup.
"""

import re
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup, Tag

from models import Listing

HEADING = re.compile(r"^(#{1,6})\s+(.+)$")
SEPARATOR = re.compile(r"^\|(?:\s*:?-{3,}:?\s*\|)+$")
LINE_BREAK = re.compile(r"</br>", re.IGNORECASE)  # a source writes its <br>s closed


@dataclass
class Table:
    section: str | None
    """The heading the table sits under, e.g. "FAANG+"."""
    headers: tuple[str, ...]
    rows: list[list[str]]


class Scraper(ABC):
    name: str

    def __init__(self, url: str) -> None:
        self.url = url

    def scrape(self) -> list[Listing]:
        return self.parse(fetch(self.url))

    @abstractmethod
    def parse(self, markdown: str) -> list[Listing]:
        """Pull listings out of a fetched README."""


def fetch(url: str) -> str:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def tables(markdown: str) -> Iterator[Table]:
    """Every Markdown table in the document, tagged with the heading it appears under."""
    lines = markdown.splitlines()
    section: str | None = None
    index = 0

    while index < len(lines):
        line = lines[index].strip()

        if heading := HEADING.match(line):
            section = heading.group(2).strip()
            index += 1
            continue

        # A table is a header row, a |---|---| separator, then rows until the pipes stop.
        is_header = (
            line.startswith("|")
            and index + 1 < len(lines)
            and SEPARATOR.match(lines[index + 1].strip())
        )
        if not is_header:
            index += 1
            continue

        headers = tuple(split_row(line))
        index += 2

        rows: list[list[str]] = []
        while index < len(lines) and lines[index].strip().startswith("|"):
            rows.append(split_row(lines[index]))
            index += 1

        yield Table(section=section, headers=headers, rows=rows)


def split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def cell_soup(cell: str) -> Tag:
    return BeautifulSoup(LINE_BREAK.sub("<br/>", cell), "html.parser")


def text_of(cell: str) -> str:
    return cell_soup(cell).get_text(strip=True)


def cell_lines(cell: str) -> list[str]:
    """A cell's text, split on the <br>s and <details> some sources use to pack in several values."""
    container: Tag = cell_soup(cell)

    details = container.find("details")
    if isinstance(details, Tag):
        if summary := details.find("summary"):
            summary.extract()  # drop the "N locations" toggle label
        container = details

    return [line.strip() for line in container.stripped_strings]


def link_href(cell: str) -> str | None:
    """The URL an Apply button points at, or None when the source marks the listing closed."""
    anchor = cell_soup(cell).find("a")
    if not isinstance(anchor, Tag):
        return None
    href = anchor.get("href")
    return href if isinstance(href, str) else None
