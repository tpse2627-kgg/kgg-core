"""Graph stores: the interface every triple store implements, and an in-memory one.

kgg-core only talks to :class:`GraphStore`. :class:`InMemoryGraphStore` is the
reference implementation used in tests. kgg-django implements the same
interface with pyoxigraph for data on disk. Both are checked by the shared
contract tests in :mod:`kgg_core.testing`.

See ``docs/decisions/0002-graph-store-interface.md`` for the reasoning.
"""

from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator

from rdflib import URIRef

from kgg_core.model import Changeset, Object, Triple

__all__ = ["GraphStore", "InMemoryGraphStore"]


def _as_triples(triples: Iterable[Triple]) -> list[Triple]:
    """Read *triples* into a list and check that each one is a :class:`Triple`.

    Reading the input first means callers can pass a live iterator over the
    same store, e.g. ``store.remove(store.triples(subject=s))``.
    """
    result = list(triples)
    for triple in result:
        if not isinstance(triple, Triple):
            raise TypeError(f"expected a Triple, got {type(triple).__name__}: {triple!r}")
    return result


class GraphStore(ABC):
    """A set of triples (one RDF graph) with add, remove and pattern queries.

    A store behaves like a set. Adding a triple that is already there, or
    removing one that is not, changes nothing and is not an error. ``add`` and
    ``remove`` return how many triples actually changed.

    Implementations must:

    - accept any iterable of :class:`~kgg_core.model.Triple` in ``add`` and
      ``remove``, including an iterator over the same store, and raise
      :class:`TypeError` for anything that is not a ``Triple``;
    - let callers write to the store while they iterate over the result of
      :meth:`triples` (it may return a snapshot);
    - compare triples by RDF term equality, as :class:`Triple` does.

    Writes go through :meth:`apply` with a :class:`~kgg_core.model.Changeset`,
    so the history stays complete. ``add`` and ``remove`` are the building
    blocks it uses.
    """

    @abstractmethod
    def add(self, triples: Iterable[Triple]) -> int:
        """Add *triples* to the store and return how many were not there before."""

    @abstractmethod
    def remove(self, triples: Iterable[Triple]) -> int:
        """Remove *triples* from the store and return how many were there."""

    @abstractmethod
    def triples(
        self,
        subject: URIRef | None = None,
        predicate: URIRef | None = None,
        object: Object | None = None,
    ) -> Iterator[Triple]:
        """Return the triples that match the pattern, in no particular order.

        ``None`` matches any term, so ``triples()`` returns all triples and
        ``triples(subject=s)`` all triples about ``s``.
        """

    @abstractmethod
    def __contains__(self, triple: object) -> bool:
        """``True`` if *triple* is in the store; ``False`` for anything that is not a Triple."""

    @abstractmethod
    def __len__(self) -> int:
        """Return the number of triples in the store."""

    def apply(self, changeset: Changeset) -> Changeset:
        """Apply *changeset* to the store and return what actually changed.

        The returned changeset has the same id, author, timestamp and source,
        but only contains the triples that were really added (not there
        before) and really removed (there before). A duplicate add or the
        removal of a missing triple therefore drops out, and a changeset that
        changes nothing comes back empty.

        This default removes and then adds, which is not atomic. Stores that
        support transactions should override it to apply both in one step.
        """
        removed = frozenset(t for t in changeset.removed if t in self)
        added = frozenset(t for t in changeset.added if t not in self)
        self.remove(removed)
        self.add(added)
        return dataclasses.replace(changeset, added=added, removed=removed)


class InMemoryGraphStore(GraphStore):
    """A :class:`GraphStore` that keeps its triples in a Python set.

    Pattern queries scan all triples, which is fine for tests and small
    graphs. Nothing is persisted; the triples are gone when the object is.
    """

    def __init__(self, triples: Iterable[Triple] = ()) -> None:
        """Create a store, optionally filled with *triples*."""
        self._triples: set[Triple] = set()
        self.add(triples)

    def add(self, triples: Iterable[Triple]) -> int:
        before = len(self._triples)
        self._triples.update(_as_triples(triples))
        return len(self._triples) - before

    def remove(self, triples: Iterable[Triple]) -> int:
        before = len(self._triples)
        self._triples.difference_update(_as_triples(triples))
        return before - len(self._triples)

    def triples(
        self,
        subject: URIRef | None = None,
        predicate: URIRef | None = None,
        object: Object | None = None,
    ) -> Iterator[Triple]:
        # Build the result as a list (a snapshot), so callers can change the
        # store while they iterate over it.
        matches = [
            t
            for t in self._triples
            if (subject is None or t.subject == subject)
            and (predicate is None or t.predicate == predicate)
            and (object is None or t.object == object)
        ]
        return iter(matches)

    def __contains__(self, triple: object) -> bool:
        return isinstance(triple, Triple) and triple in self._triples

    def __len__(self) -> int:
        return len(self._triples)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({len(self)} triples)"
