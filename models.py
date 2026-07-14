"""Shared listing model, common to every source."""

from dataclasses import dataclass


@dataclass
class Listing:
    source: str
    company: str
    role: str
    locations: list[str]
    url: str | None
    posted: str
    """How the source dates the listing: an absolute date ("Jul 09") or an age ("7d")."""
    salary: str | None = None
    category: str | None = None
    """The section of the source's README the listing came from, when it has sections."""

    @property
    def is_open(self) -> bool:
        return self.url is not None

    def __str__(self) -> str:
        title = f"{self.company} — {self.role}"
        if self.category:
            title += f"  [{self.category}]"

        lines = [
            title,
            f"  Location:  {' | '.join(self.locations) or '-'}",
            f"  Posted:    {self.posted}",
        ]
        if self.salary:
            lines.append(f"  Salary:    {self.salary}")
        lines.append(f"  Apply:     {self.url or 'closed 🔒'}")
        return "\n".join(lines)
