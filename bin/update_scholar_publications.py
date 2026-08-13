#!/usr/bin/env python
"""
Auto-sync publications from Google Scholar into _bibliography/papers.bib.

For each paper on the author's Google Scholar profile, this script checks
whether it already exists in papers.bib (matched by title). If not, it
appends a minimal BibTeX stub so the publication page stays up to date.

The BibTeX stub is intentionally minimal — fill in the journal/venue,
DOI, abstract, etc. manually after the script adds it.

Run manually:  python bin/update_scholar_publications.py
Runs via:       .github/workflows/update-publications.yml (weekly)
"""

import os
import re
import sys

import yaml
from scholarly import scholarly


BIB_FILE = "_bibliography/papers.bib"


def load_scholar_user_id() -> str:
    config_file = "_data/socials.yml"
    if not os.path.exists(config_file):
        print(f"Config file {config_file} not found.")
        sys.exit(1)
    try:
        with open(config_file) as f:
            config = yaml.safe_load(f)
        scholar_id = config.get("scholar_userid")
        if not scholar_id:
            print("No 'scholar_userid' in _data/socials.yml.")
            sys.exit(1)
        return scholar_id
    except yaml.YAMLError as e:
        print(f"YAML parse error in {config_file}: {e}")
        sys.exit(1)


def extract_existing_titles(bib_content: str) -> set:
    """Return a set of lowercased titles already in papers.bib."""
    titles = set()
    for m in re.finditer(r"title\s*=\s*[\{\"](.*?)[\}\"]", bib_content, re.IGNORECASE | re.DOTALL):
        titles.add(re.sub(r"\s+", " ", m.group(1)).lower().strip())
    return titles


def make_bibtex_key(authors: str, year: str, existing_keys: set) -> str:
    """Generate a unique BibTeX key like XuEtAl2024."""
    first = authors.split(" and ")[0].split(",")
    last_name = first[0].strip().replace(" ", "")
    base = f"{last_name}{year}"
    key = base
    suffix = 97  # 'a'
    while key in existing_keys:
        key = f"{base}{chr(suffix)}"
        suffix += 1
    existing_keys.add(key)
    return key


def extract_existing_keys(bib_content: str) -> set:
    return set(re.findall(r"@\w+\{(\w+),", bib_content))


def incompleteness_reasons(bib: dict) -> list[str]:
    """Return why a Scholar publication's metadata isn't usable, or [] if it's fine.

    Scholar's author-level fetch often returns a shallow record for a given
    publication (no author string, no year) unless that entry is deep-filled
    individually. Rather than writing "Unknown Author" / "????" straight into
    papers.bib, we skip those and retry on the next scheduled run.
    """
    reasons = []
    if not bib.get("title", "").strip():
        reasons.append("missing title")
    author = bib.get("author", "").strip()
    if not author or author.lower() == "unknown author":
        reasons.append("missing author")
    year = str(bib.get("pub_year", "")).strip()
    if not year.isdigit():
        reasons.append("missing/invalid year")
    return reasons


def pub_to_bibtex_stub(pub: dict, existing_keys: set) -> tuple[str, str]:
    """Convert a scholarly publication dict to a minimal BibTeX entry."""
    bib = pub.get("bib", {})
    title = bib.get("title", "").replace("{", "").replace("}", "")
    authors = bib.get("author", "")
    year = str(bib.get("pub_year", ""))
    venue = bib.get("venue", "")
    abstract = bib.get("abstract", "")

    key = make_bibtex_key(authors, year, existing_keys)

    # Guess entry type
    if any(x in venue.lower() for x in ["arxiv", "preprint", "biorxiv"]):
        entry_type = "misc"
    elif bib.get("journal"):
        entry_type = "article"
    else:
        entry_type = "inproceedings"

    lines = [f"@{entry_type}{{{key},"]
    lines.append(f"  bibtex_show = {{true}},")
    lines.append(f"  title = {{{title}}},")
    lines.append(f"  author = {{{authors}}},")
    lines.append(f"  year = {{{year}}},")

    if bib.get("journal"):
        lines.append(f"  journal = {{{bib['journal']}}},")
    elif venue:
        lines.append(f"  booktitle = {{{venue}}},")

    if abstract:
        short_abstract = abstract[:500] + ("..." if len(abstract) > 500 else "")
        lines.append(f"  abstract = {{{short_abstract}}},")

    lines.append("}")
    return key, "\n".join(lines)


def main() -> None:
    scholar_id = load_scholar_user_id()
    print(f"Fetching publications for Google Scholar ID: {scholar_id}")

    # Read existing papers.bib
    if os.path.exists(BIB_FILE):
        with open(BIB_FILE) as f:
            bib_content = f.read()
    else:
        bib_content = "---\n---\n\n"

    existing_titles = extract_existing_titles(bib_content)
    existing_keys = extract_existing_keys(bib_content)

    scholarly.set_timeout(15)
    scholarly.set_retries(2)
    try:
        author = scholarly.search_author_id(scholar_id)
        author_data = scholarly.fill(author, sections=["publications"])
    except Exception as e:
        print(f"Error fetching author data: {e}")
        sys.exit(1)

    publications = author_data.get("publications", [])
    print(f"Found {len(publications)} publications on Google Scholar.")

    new_entries = []
    skipped = []
    for pub in publications:
        bib = pub.get("bib", {})
        raw_title = bib.get("title", "")
        norm_title = re.sub(r"\s+", " ", raw_title).lower().strip()
        if norm_title and norm_title in existing_titles:
            print(f"  [exists] {raw_title}")
            continue

        reasons = incompleteness_reasons(bib)
        if reasons:
            label = raw_title or "(untitled)"
            print(f"  [skipped-incomplete] {label} -- {', '.join(reasons)}")
            skipped.append(f"{label} -- {', '.join(reasons)}")
            continue

        print(f"  [new]    {raw_title}")
        _, entry = pub_to_bibtex_stub(pub, existing_keys)
        new_entries.append(entry)
        existing_titles.add(norm_title)

    if skipped:
        print(f"\n{len(skipped)} publication(s) skipped due to incomplete Scholar metadata "
              f"(will retry next run; add manually if this persists):")
        for line in skipped:
            print(f"  - {line}")

    if not new_entries:
        print("No new publications to add.")
        return

    with open(BIB_FILE, "w") as f:
        f.write(bib_content.rstrip() + "\n\n")
        for entry in new_entries:
            f.write(entry + "\n\n")

    print(f"Added {len(new_entries)} new publication(s) to {BIB_FILE}.")
    print("Remember to fill in DOIs, abstracts, and other fields manually.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
