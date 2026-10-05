"""PKHosting: Domain Name Idea Generator (source ZR-26-00740).

A Streamlit app that turns keywords into domain name ideas: prefix/suffix
combos, keyword mashups, TLD options, length filters, a heuristic
"taken-risk" label, and a best-effort DNS resolution check (clearly labeled
as best-effort — NOT a registrar availability lookup).
"""

from __future__ import annotations

import csv
import io
import os
import re
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed

import streamlit as st

# ---------------------------------------------------------------------------
# Pure logic (import-safe: no Streamlit calls in here)
# ---------------------------------------------------------------------------

PREFIXES = [
    "get", "my", "try", "go", "e", "i", "pro", "super", "best", "top",
    "new", "ultra", "hyper", "smart", "easy", "prime",
]
SUFFIXES = [
    "hub", "ly", "lab", "labs", "pro", "store", "zone", "spot", "base",
    "nest", "wise", "ship", "stack", "cloud", "host", "ify", "ster",
]
NUMBER_BITS = ["24", "365", "360", "101", "hq"]

POPULAR_TLDS = [".com", ".pk", ".net", ".io", ".org", ".co", ".dev", ".app",
                ".tech", ".store", ".online", ".site"]

# Optional overrides via environment variables (see .env.example).
DNS_TIMEOUT_SECONDS = float(os.getenv("DNS_TIMEOUT_SECONDS", "3.0"))
DEFAULT_MAX_LENGTH = int(os.getenv("DEFAULT_MAX_LENGTH", "15"))


def clean_keyword(raw: str) -> str:
    """Lowercase, strip, keep only a-z and 0-9."""
    return re.sub(r"[^a-z0-9]", "", raw.strip().lower())


def parse_keywords(text: str) -> list[str]:
    parts = re.split(r"[,\s]+", text or "")
    seen: list[str] = []
    for p in parts:
        kw = clean_keyword(p)
        if kw and kw not in seen:
            seen.append(kw)
    return seen


def generate_domain_ideas(
    keywords: list[str],
    tlds: list[str],
    max_len: int = 15,
    use_prefixes: bool = True,
    use_suffixes: bool = True,
    combine_keywords: bool = True,
    allow_hyphens: bool = False,
    allow_numbers: bool = False,
) -> list[dict]:
    """Build candidate (name, tld) pairs. Returns dicts with domain info."""
    names: list[tuple[str, str]] = []  # (name, how-it-was-made)

    for kw in keywords:
        names.append((kw, "keyword"))

    if combine_keywords and len(keywords) > 1:
        for i, a in enumerate(keywords):
            for b in keywords[i + 1:]:
                names.append((a + b, "keyword mashup"))
                names.append((b + a, "keyword mashup"))
                if allow_hyphens:
                    names.append((f"{a}-{b}", "hyphenated mashup"))

    if use_prefixes:
        for kw in keywords:
            for pre in PREFIXES:
                names.append((pre + kw, "prefix"))

    if use_suffixes:
        for kw in keywords:
            for suf in SUFFIXES:
                names.append((kw + suf, "suffix"))

    if allow_numbers:
        for kw in keywords:
            for num in NUMBER_BITS:
                names.append((kw + num, "with number"))
                names.append((num + kw, "with number"))

    if allow_hyphens:
        for kw in keywords:
            names.append((f"my-{kw}", "hyphenated"))
            names.append((f"{kw}-hub", "hyphenated"))

    # Deduplicate, filter length, expand across TLDs
    seen_names: set[str] = set()
    results: list[dict] = []
    for name, made_how in names:
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        if len(name) > max_len:
            continue
        for tld in tlds:
            domain = f"{name}{tld}"
            results.append(
                {
                    "domain": domain,
                    "name": name,
                    "tld": tld,
                    "length": len(name),
                    "style": made_how,
                    "heuristic": heuristic_taken_risk(name, tld, made_how),
                }
            )
    results.sort(key=lambda r: (r["length"], r["domain"]))
    return results


def heuristic_taken_risk(name: str, tld: str, style: str) -> str:
    """Heuristic label only — never a real availability claim."""
    if len(name) <= 4 and tld in (".com", ".net", ".org", ".io"):
        return "Very likely taken (heuristic)"
    if style == "keyword" and tld == ".com":
        return "Very likely taken (heuristic)"
    if len(name) <= 6 and tld == ".com":
        return "Likely taken (heuristic)"
    if "-" in name or any(ch.isdigit() for ch in name):
        return "Lower competition (heuristic)"
    return "Unknown — check a registrar"


def dns_resolves(domain: str, timeout: float | None = None) -> bool | None:
    if timeout is None:
        timeout = DNS_TIMEOUT_SECONDS
    """Best-effort DNS A-record check.

    Returns True if the name resolves, False if it does not, None on error.
    A resolving name is very likely taken; a non-resolving name may still be
    registered (parked / no DNS). This is NOT a registrar availability check.
    """
    try:
        socket.setdefaulttimeout(timeout)
        socket.gethostbyname(domain)
        return True
    except socket.gaierror:
        return False
    except (OSError, UnicodeError):
        return None
    finally:
        socket.setdefaulttimeout(None)


def batch_dns_check(domains: list[str], max_workers: int = 20) -> dict[str, bool | None]:
    out: dict[str, bool | None] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {pool.submit(dns_resolves, d): d for d in domains}
        for fut in as_completed(future_map):
            out[future_map[fut]] = fut.result()
    return out


def dns_label(status: bool | None) -> str:
    if status is True:
        return "Resolves — likely taken"
    if status is False:
        return "No DNS record — may still be registered"
    return "Check failed"


def ideas_to_csv(ideas: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=["domain", "name", "tld", "length", "style",
                         "heuristic", "dns"]
    )
    writer.writeheader()
    for idea in ideas:
        writer.writerow({k: idea.get(k, "") for k in writer.fieldnames})
    return buf.getvalue()
