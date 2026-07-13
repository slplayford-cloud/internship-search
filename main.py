import os
import re
import sys

import dotenv
import requests

SECTION_HEADING = re.compile(r"^##\s+.*USA SWE Internships", re.IGNORECASE)
NEXT_SECTION = re.compile(r"^##\s")
SUBSECTION = re.compile(r"^###\s+(.*)")
TABLE_ROW = re.compile(r"^\|(.+)\|\s*$")
SEPARATOR_ROW = re.compile(r"^\|[\s:|-]+\|\s*$")
LINK = re.compile(r'<a\s+href="([^"]+)"', re.IGNORECASE)
TAGS = re.compile(r"<[^>]+>")

COLOR = sys.stdout.isatty() and os.getenv("NO_COLOR") is None
BOLD, DIM, CYAN, GREEN, YELLOW, BLUE, RESET = (
    "\033[1m",
    "\033[2m",
    "\033[36m",
    "\033[32m",
    "\033[33m",
    "\033[34m",
    "\033[0m",
)


def paint(text: str, *styles: str) -> str:
    return f"{''.join(styles)}{text}{RESET}" if COLOR else text


def fetch(url: str) -> str:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.text


def usa_internships_section(markdown: str) -> list[str]:
    lines = markdown.splitlines()
    start = next(i for i, line in enumerate(lines) if SECTION_HEADING.match(line))
    for end in range(start + 1, len(lines)):
        if NEXT_SECTION.match(lines[end]):
            return lines[start:end]
    return lines[start:]


def split_cells(row: str) -> list[str]:
    return [cell.strip() for cell in TABLE_ROW.match(row).group(1).split("|")]


def cell_text(cell: str) -> str:
    return TAGS.sub("", cell).strip()


def cell_link(cell: str) -> str | None:
    match = LINK.search(cell)
    return match.group(1) if match else None


def parse_jobs(lines: list[str]) -> list[dict]:
    jobs = []
    category = ""
    columns: list[str] = []

    for line in lines:
        subsection = SUBSECTION.match(line)
        if subsection:
            category = subsection.group(1).strip()
            columns = []
            continue

        if not TABLE_ROW.match(line):
            columns = []
            continue

        if SEPARATOR_ROW.match(line):
            continue

        cells = split_cells(line)

        # The first table row is the header; tables vary (Other has no Salary).
        if not columns:
            columns = [cell_text(cell) for cell in cells]
            continue

        job = {"category": category}
        for column, cell in zip(columns, cells):
            job[column.lower()] = cell_text(cell)
            link = cell_link(cell)
            if link:
                job[f"{column.lower()}_url"] = link
        jobs.append(job)

    return jobs


def main():
    dotenv.load_dotenv()
    url = os.getenv("REPO_URL")
    if not url:
        sys.exit("REPO_URL is not set (add it to .env)")

    jobs = parse_jobs(usa_internships_section(fetch(url)))

    for job in jobs:
        category = paint(f"[{job['category']}]", DIM)
        company = paint(job["company"], BOLD, CYAN)
        print(f"{category} {company} — {job['position']}")
        print(f"  {paint('location:', DIM)} {job['location']}")
        print(f"  {paint('salary:  ', DIM)} {paint(job.get('salary', 'n/a'), GREEN)}")
        print(f"  {paint('age:     ', DIM)} {paint(job['age'], YELLOW)}")
        print(f"  {paint('company: ', DIM)} {paint(job.get('company_url', 'n/a'), BLUE)}")
        print(f"  {paint('apply:   ', DIM)} {paint(job.get('posting_url', 'n/a'), BLUE)}")
        print()

    print(paint(f"{len(jobs)} US internship postings", BOLD))


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        # Reader closed early (e.g. `| head`); redirect stdout so the
        # interpreter doesn't re-raise while flushing at shutdown.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(1)
