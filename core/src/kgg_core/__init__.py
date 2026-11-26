"""Python core of the Knowledge Graph Generator, plain logic without Django."""

from kgg_core.model import Changeset, Triple

__all__ = ["Changeset", "Triple", "health"]


def health() -> str:
    return "ok"
