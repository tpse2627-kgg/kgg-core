"""Core data model of the Knowledge Graph Generator: triples and changesets.

A :class:`Triple` is one RDF statement. A :class:`Changeset` groups the triples
that one write adds and removes, together with who made it, when and from
where. Every change to a graph is described by a changeset, which is what the
history and the LDES stream are built from.

See ``docs/decisions/0001-triple-and-changeset-model.md`` for the reasoning.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from rdflib import Literal, URIRef

__all__ = ["Changeset", "Object", "Triple"]

Object = URIRef | Literal
"""The terms allowed in the object position of a triple."""

# An absolute IRI starts with a scheme (RFC 3986, section 3.1) ...
_IRI_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")
# ... and contains none of the characters RFC 3987 excludes. rdflib accepts
# them with a warning, but pyoxigraph rejects them, so we reject them up front.
_IRI_FORBIDDEN = re.compile(r'[\x00-\x20<>"{}|^`\\]')


def _check_iri(term: object, position: str) -> None:
    if not isinstance(term, URIRef):
        raise TypeError(f"{position} must be a URIRef, got {type(term).__name__}: {term!r}")
    if not _IRI_SCHEME.match(term) or _IRI_FORBIDDEN.search(term):
        raise ValueError(f"{position} is not a valid absolute IRI: {str(term)!r}")


@dataclass(frozen=True, slots=True)
class Triple:
    """One RDF statement: *subject* *predicate* *object*.

    The terms are rdflib terms. The subject and predicate are IRIs
    (:class:`~rdflib.URIRef`), the object is an IRI or a
    :class:`~rdflib.Literal`. Blank nodes are not accepted, because they have
    no stable identity and could not be edited or deleted later. Plain strings
    are not accepted either, since ``"Alice"`` could mean an IRI or a literal.

    Triples are immutable and hashable, so they can be used in sets and as
    dictionary keys. Two triples are equal when their terms are equal under
    RDF term equality (a literal's datatype and language tag count).

    Raises:
        TypeError: if a term has the wrong type.
        ValueError: if an IRI is not a valid absolute IRI.
    """

    subject: URIRef
    predicate: URIRef
    object: Object

    def __post_init__(self) -> None:
        _check_iri(self.subject, "subject")
        _check_iri(self.predicate, "predicate")
        if isinstance(self.object, URIRef):
            _check_iri(self.object, "object")
        elif not isinstance(self.object, Literal):
            raise TypeError(
                f"object must be a URIRef or Literal, got {type(self.object).__name__}: {self.object!r}"
            )

    @classmethod
    def from_tuple(cls, terms: tuple[object, object, object]) -> Triple:
        """Build a triple from an rdflib ``(s, p, o)`` tuple, e.g. from ``Graph.triples()``."""
        subject, predicate, obj = terms
        return cls(subject, predicate, obj)  # type: ignore[arg-type]

    def as_tuple(self) -> tuple[URIRef, URIRef, Object]:
        """Return the triple as an rdflib ``(s, p, o)`` tuple, e.g. for ``Graph.add()``."""
        return (self.subject, self.predicate, self.object)

    def n3(self) -> str:
        """Return the triple as one line of N-Triples, e.g. for logs and error messages."""
        return f"{self.subject.n3()} {self.predicate.n3()} {self.object.n3()} ."


@dataclass(frozen=True)
class Changeset:
    """One write to a graph: the triples it adds and removes, and its metadata.

    An update of a triple is a single changeset that removes the old triple and
    adds the new one. A triple cannot be in both ``added`` and ``removed``, so
    applying a changeset gives the same result whatever the order of the two
    steps. An empty changeset is valid; see :attr:`is_empty`.

    Use :meth:`create` to make a new changeset; it generates the ``id`` and
    the ``timestamp``. The constructor is for rebuilding a stored changeset.

    Attributes:
        id: Unique id of the changeset, later used as the LDES member id.
        added: Triples the changeset adds to the graph.
        removed: Triples the changeset removes from the graph.
        author: Who made the change, e.g. a user name or a client system.
        timestamp: When the change was made, always timezone-aware UTC.
        source: Where the triples come from, e.g. a file name or an API
            client, or ``None`` if unknown.

    Raises:
        TypeError: if ``added`` or ``removed`` contains something other than
            a :class:`Triple`, or ``id`` is not a :class:`uuid.UUID`.
        ValueError: if a triple is both added and removed, ``author`` is
            empty, or ``timestamp`` has no timezone.
    """

    id: uuid.UUID
    added: frozenset[Triple]
    removed: frozenset[Triple]
    author: str
    timestamp: datetime
    source: str | None = None

    def __post_init__(self) -> None:
        # Accept any iterable and store it as a frozenset, so a changeset is
        # immutable and hashable however it was built.
        added = frozenset(self.added)
        removed = frozenset(self.removed)
        for triple in added | removed:
            if not isinstance(triple, Triple):
                raise TypeError(
                    f"changesets contain Triple objects, got {type(triple).__name__}: {triple!r}"
                )
        overlap = added & removed
        if overlap:
            listed = ", ".join(sorted(t.n3() for t in overlap))
            raise ValueError(f"triples cannot be both added and removed: {listed}")
        if not isinstance(self.id, uuid.UUID):
            raise TypeError(f"id must be a UUID, got {type(self.id).__name__}")
        if not self.author or not self.author.strip():
            raise ValueError("author must not be empty")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")

        object.__setattr__(self, "added", added)
        object.__setattr__(self, "removed", removed)
        object.__setattr__(self, "timestamp", self.timestamp.astimezone(UTC))

    @classmethod
    def create(
        cls,
        *,
        added: Iterable[Triple] = (),
        removed: Iterable[Triple] = (),
        author: str,
        source: str | None = None,
    ) -> Changeset:
        """Make a new changeset with a fresh id and the current time as timestamp."""
        return cls(
            id=uuid.uuid4(),
            added=frozenset(added),
            removed=frozenset(removed),
            author=author,
            timestamp=datetime.now(UTC),
            source=source,
        )

    @property
    def is_empty(self) -> bool:
        """``True`` if the changeset neither adds nor removes any triple."""
        return not self.added and not self.removed
