"""Source admission rules for the current curated Kenya Airways corpus."""

# These uploads have no verifiable official provenance and contain misleading or
# unreadable baggage text. Remove them from this set only after validating the
# replacement source and updating evaluation/source_inventory.csv.
UNVERIFIED_POLICY_SOURCES = frozenset(
    {"Kenya_Airways_Policy.pdf", "Kenya_Airways_Rule.pdf"}
)


def is_verified_policy_source(source: str | None) -> bool:
    """Exclude explicitly unverified filenames from active RAG retrieval."""
    source_name = (source or "").replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    prefix, separator, filename = source_name.partition("_")
    if (
        separator
        and len(prefix) == 32
        and all(character in "0123456789abcdef" for character in prefix.casefold())
    ):
        source_name = filename
    excluded_names = {name.casefold() for name in UNVERIFIED_POLICY_SOURCES}
    return source_name.casefold() not in excluded_names
