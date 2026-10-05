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


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="PKHosting Domain Idea Generator",
                       page_icon="🌐", layout="wide")
    st.title("🌐 PKHosting: Domain Name Idea Generator")
    st.caption(
        "Turn keywords into domain name ideas. Heuristic labels and the "
        "best-effort DNS check are guidance only — always confirm real "
        "availability with a domain registrar before buying."
    )

    with st.sidebar:
        st.header("Settings")
        keywords_text = st.text_input(
            "Keywords (comma or space separated)",
            value="host, cloud, web",
            help="e.g. host, cloud, web",
        )
        tlds = st.multiselect("TLDs", POPULAR_TLDS,
                              default=[".com", ".pk", ".net", ".io"])
        max_len = st.slider("Max name length (before the dot)", 3, 25, DEFAULT_MAX_LENGTH)
        st.subheader("Wordplay")
        use_prefixes = st.checkbox("Add prefixes (get-, my-, pro- …)", value=True)
        use_suffixes = st.checkbox("Add suffixes (-hub, -ly, -labs …)", value=True)
        combine = st.checkbox("Combine keywords (hostcloud)", value=True)
        allow_hyphens = st.checkbox("Allow hyphens", value=False)
        allow_numbers = st.checkbox("Allow numbers", value=False)
        generate = st.button("✨ Generate ideas", type="primary",
                             use_container_width=True)

    if generate:
        keywords = parse_keywords(keywords_text)
        if not keywords:
            st.error("Please enter at least one keyword.")
            return
        if not tlds:
            st.error("Please select at least one TLD.")
            return
        ideas = generate_domain_ideas(
            keywords, tlds, max_len=max_len, use_prefixes=use_prefixes,
            use_suffixes=use_suffixes, combine_keywords=combine,
            allow_hyphens=allow_hyphens, allow_numbers=allow_numbers,
        )
        for idea in ideas:
            idea["dns"] = ""
        st.session_state["ideas"] = ideas
        st.session_state["dns_done"] = False

    ideas: list[dict] = st.session_state.get("ideas", [])
    if not ideas:
        st.info("Enter keywords in the sidebar and hit **Generate ideas**.")
        return

    st.subheader(f"💡 {len(ideas)} ideas")
    st.caption(
        "*Heuristic labels are rough guesses based on name length, TLD and "
        "style — they are not availability checks.*"
    )

    col_a, col_b = st.columns([1, 1])
    with col_a:
        dns_cap = st.slider("DNS check: how many (shortest first)?",
                            10, 200, 50, step=10)
    with col_b:
        st.write("")
        st.write("")
        run_dns = st.button("🔍 Run best-effort DNS check",
                            use_container_width=True)

    if run_dns:
        targets = [i["domain"] for i in ideas[:dns_cap]]
        progress = st.progress(0, text="Checking DNS…")
        results = batch_dns_check(targets)
        for idx, idea in enumerate(ideas):
            if idea["domain"] in results:
                idea["dns"] = dns_label(results[idea["domain"]])
        progress.progress(1.0, text="DNS check complete.")
        st.session_state["dns_done"] = True
        st.info(
            "Best-effort DNS check only: a resolving domain is very likely "
            "taken, but a non-resolving domain may still be registered "
            "(parked or DNS-less). Confirm with a registrar."
        )

    table = [
        {
            "Domain": i["domain"],
            "Length": i["length"],
            "TLD": i["tld"],
            "Style": i["style"],
            "Heuristic": i["heuristic"],
            "DNS": i.get("dns", ""),
        }
        for i in ideas
    ]
    st.dataframe(table, use_container_width=True, hide_index=True)

    st.download_button(
        "⬇️ Download ideas as CSV",
        data=ideas_to_csv(ideas),
        file_name="domain-ideas.csv",
        mime="text/csv",
        use_container_width=False,
    )


if __name__ == "__main__":
    main()
