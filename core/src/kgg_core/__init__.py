"""Python core of the Knowledge Graph Generator, plain logic without Django."""

from kgg_core.model import Changeset, Triple
from kgg_core.store import GraphStore, InMemoryGraphStore

__all__ = ["Changeset", "GraphStore", "InMemoryGraphStore", "Triple", "health"]


def health() -> str:
    return "ok"
