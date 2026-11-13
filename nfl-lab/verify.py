#!/usr/bin/env python3
"""Audit the canonical NFL vertical for local links and sourced/flagged table rows.

A passing result means each data row has either a first-party NFL citation or an
explicit uncertainty/pending marker. It does not verify model validity or facts.
"""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(__file__).resolve().parent
OFFICIAL_HOSTS = {"nfl.com", "www.nfl.com", "operations.nfl.com"}
PAGES = sorted({*REPO.glob("nfl-*.html"), REPO / "nfl-strategy.html", ROOT / "sources.html"})


class AuditParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = []
        self.tables = []
        self.row = None
        self.in_td = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self.hrefs.append(attrs["href"])
        if tag == "table":
            self.tables.append([])
        elif tag == "tr" and self.tables:
            self.row = {"cells": 0, "official_link": False, "flagged": False, "text": ""}
        elif tag in {"td", "th"} and self.row is not None:
            self.in_td = tag == "td"
            if self.in_td:
                self.row["cells"] += 1
        elif self.row is not None and tag in {"span", "strong", "em"}:
            classes = set(attrs.get("class", "").split())
            if classes.intersection({"flag", "unverified", "est", "pending"}):
                self.row["flagged"] = True
        elif tag == "a" and self.in_td and self.row is not None and attrs.get("href"):
            host = (urlparse(attrs["href"]).hostname or "").lower()
            if host in OFFICIAL_HOSTS:
                self.row["official_link"] = True

    def handle_data(self, data):
        if self.row is not None:
            text = data.strip().lower()
            self.row["text"] += " " + text
            if any(word in text for word in ("unverified", "not verified", "pending", "flagged", "open —", "proposed", "project-only")):
                self.row["flagged"] = True

    def handle_endtag(self, tag):
        if tag in {"td", "th"}:
            self.in_td = False
        elif tag == "tr" and self.row is not None:
            if self.row["cells"]:
                self.tables[-1].append(self.row)
            self.row = None


def main():
    errors, flagged_rows = [], 0
    total_rows = 0
    for page in PAGES:
        if not page.exists():
            errors.append(f"missing expected page: {page.relative_to(REPO)}")
            continue
        parser = AuditParser()
        parser.feed(page.read_text(encoding="utf-8"))
        for href in parser.hrefs:
            parsed = urlparse(href)
            if parsed.scheme or href.startswith("#"):
                continue
            target = (page.parent / parsed.path).resolve()
            if not target.exists():
                errors.append(f"{page.relative_to(REPO)}: broken local link {href}")
        for table_number, rows in enumerate(parser.tables, start=1):
            for row_number, row in enumerate(rows, start=1):
                total_rows += 1
                if row["official_link"]:
                    continue
                if row["flagged"]:
                    flagged_rows += 1
                    continue
                errors.append(f"{page.relative_to(REPO)} table {table_number} row {row_number}: no first-party NFL source and no explicit flagged/unverified marker")
    if errors:
        print("NFL vertical verification FAILED:")
        print("\n".join(errors))
        raise SystemExit(1)
    print(f"NFL vertical verification passed: {len(PAGES)} pages, {total_rows} table rows; rows have a first-party NFL source or an explicit flagged/unverified marker ({flagged_rows} flagged rows).")


if __name__ == "__main__":
    main()
