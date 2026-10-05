"""PKHosting: Domain Name Idea Generator (source ZR-26-00740).

A Streamlit app that turns keywords into domain name ideas: prefix/suffix
combos, keyword mashups, TLD options, length filters, and a heuristic
"taken-risk" label.
"""

from __future__ import annotations

import csv
import io
import re

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


def ideas_to_csv(ideas: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=["domain", "name", "tld", "length", "style",
                         "heuristic"]
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
        "Turn keywords into domain name ideas. Heuristic labels are rough "
        "guesses only — always confirm real availability with a domain "
        "registrar before buying."
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
        max_len = st.slider("Max name length (before the dot)", 3, 25, 15)
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
        st.session_state["ideas"] = ideas

    ideas: list[dict] = st.session_state.get("ideas", [])
    if not ideas:
        st.info("Enter keywords in the sidebar and hit **Generate ideas**.")
        return

    st.subheader(f"💡 {len(ideas)} ideas")
    st.caption(
        "*Heuristic labels are rough guesses based on name length, TLD and "
        "style — they are not availability checks.*"
    )

    table = [
        {
            "Domain": i["domain"],
            "Length": i["length"],
            "TLD": i["tld"],
            "Style": i["style"],
            "Heuristic": i["heuristic"],
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
