"""Scraper for vanshb03/Summer2027-Internships.

One table. Closed listings show a 🔒 instead of an Apply link, and a company posting several
roles is named only on the first of them — the rest carry a "↳".
"""

from models import Listing
from scrapers.base import Scraper, cell_lines, link_href, tables, text_of

COLUMNS = ("Company", "Role", "Location", "Application/Link", "Date Posted")
SAME_COMPANY_AS_ABOVE = "↳"


class Summer2027Scraper(Scraper):
    name = "Summer2027-Internships"

    def parse(self, markdown: str) -> list[Listing]:
        listings: list[Listing] = []
        found_table = False

        for table in tables(markdown):
            if table.headers != COLUMNS:
                continue
            found_table = True

            for row in table.rows:
                if len(row) != len(COLUMNS):
                    continue
                company, role, location, apply_link, date_posted = row

                company = text_of(company)
                if company == SAME_COMPANY_AS_ABOVE and listings:
                    company = listings[-1].company

                listings.append(
                    Listing(
                        source=self.name,
                        company=company,
                        role=text_of(role),
                        locations=cell_lines(location),
                        url=link_href(apply_link),
                        posted=text_of(date_posted),
                    )
                )

        if not found_table:
            raise LookupError(f"no table with headers {COLUMNS}")
        return listings
