"""Shared normalization for certified templates and lexical matching."""

import re


def normalize(text: str) -> str:
    """Normalize approved aliases and natural-language template keys."""
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))
