#!/usr/bin/env python3
"""Structural/source-link audit for the NFL Decision Lab static pages.

This does not verify that a strategy works or that external pages remain unchanged.
"""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
OFFICIAL_HOSTS = {"nfl.com", "www.nfl.com", "operations.nfl.com"}
PAGES = sorted(ROOT.glob("*.html"))


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
            self.row = {"cells": 0, "official_link": False}
        elif tag in {"td", "th"} and self.row is not None:
            self.in_td = tag == "td"
            if self.in_td:
                self.row["cells"] += 1
        elif tag == "a" and self.in_td and self.row is not None and attrs.get("href"):
            host = (urlparse(attrs["href"]).hostname or "").lower()
            if host in OFFICIAL_HOSTS:
                self.row["official_link"] = True

    def handle_endtag(self, tag):
        if tag in {"td", "th"}:
            self.in_td = False
        elif tag == "tr" and self.row is not None:
            if self.row["cells"]:
                self.tables[-1].append(self.row)
            self.row = None


def main():
    errors = []
    for page in PAGES:
        parser = AuditParser()
        parser.feed(page.read_text(encoding="utf-8"))
        for href in parser.hrefs:
            parsed = urlparse(href)
            if parsed.scheme or href.startswith("#"):
                continue
            target = (page.parent / parsed.path).resolve()
            if not target.exists():
                errors.append(f"{page.relative_to(ROOT)}: broken local link {href}")
        for table_number, rows in enumerate(parser.tables, start=1):
            for row_number, row in enumerate(rows, start=1):
                if not row["official_link"]:
                    errors.append(f"{page.relative_to(ROOT)} table {table_number} row {row_number}: no official NFL source link")
    if errors:
        print("NFL lab verification FAILED:")
        print("\n".join(errors))
        raise SystemExit(1)
    # Emit a useful audited row count.
    total = 0
    for page in PAGES:
        parser = AuditParser()
        parser.feed(page.read_text(encoding="utf-8"))
        total += sum(len(table) for table in parser.tables)
    print(f"Audited {total} data rows; source links are first-party NFL / NFL Operations URLs.")


if __name__ == "__main__":
    main()
