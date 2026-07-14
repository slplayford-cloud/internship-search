"""Scraper for speedyapply/2027-SWE-College-Jobs.

A table per section (FAANG+, Quant, Other). The FAANG+ and Quant tables carry a Salary column
that Other lacks, the company cell links to the company's site, and listings are dated by age
("7d") rather than by post date. The source has no marker for a closed listing.
"""

from models import Listing
from scrapers.base import Scraper, cell_lines, link_href, tables, text_of

COLUMNS = ("Company", "Position", "Location", "Posting", "Age")
COLUMNS_WITH_SALARY = ("Company", "Position", "Location", "Salary", "Posting", "Age")


class SpeedyApplyScraper(Scraper):
    name = "2027-SWE-College-Jobs"

    def parse(self, markdown: str) -> list[Listing]:
        listings: list[Listing] = []
        found_table = False

        for table in tables(markdown):
            has_salary = table.headers == COLUMNS_WITH_SALARY
            if not has_salary and table.headers != COLUMNS:
                continue
            found_table = True

            for row in table.rows:
                if len(row) != len(table.headers):
                    continue

                company, role, location, *rest = row
                salary = rest.pop(0) if has_salary else None
                apply_link, age = rest

                listings.append(
                    Listing(
                        source=self.name,
                        company=text_of(company),
                        role=text_of(role),
                        locations=cell_lines(location),
                        url=link_href(apply_link),
                        posted=text_of(age),
                        salary=text_of(salary) if salary else None,
                        category=table.section,
                    )
                )

        if not found_table:
            raise LookupError(f"no table with headers {COLUMNS} or {COLUMNS_WITH_SALARY}")
        return listings
