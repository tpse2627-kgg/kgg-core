# 0001: Data model for triples and changesets

**Status:** proposed · **Date:** 26.11.2026 · **Issue:** [#17](https://github.com/tpse2627-kgg/kgg-core/issues/17)

## Context

Everything in kgg-core builds on two types. The `GraphStore` (#18) stores triples, the changeset functions (#19) describe every write, and LDES versioning and the REST API in kgg-django build on both. Track B implements the same store with pyoxigraph (tpse2627-kgg/kgg-django#4), so the model must mean the same thing in both stores.

## Decision

Both types live in `kgg_core/model.py` and use rdflib terms.

**`Triple`** is a frozen, hashable dataclass with `subject`, `predicate` and `object`.

- The subject and the predicate are `URIRef`s. The object is a `URIRef` or a `Literal`.
- **Blank nodes are rejected.** They have no stable identity, so a client could not edit or delete them over the API, and pyoxigraph renames them. Data that contains blank nodes (OWL restrictions, RDF lists) will be skolemised when it comes in: each blank node is replaced by a generated IRI (rdflib `Graph.skolemize()`, `/.well-known/genid/…`). That is a separate, later issue.
- **Plain strings are rejected**, because `"Alice"` could mean an IRI or a literal.
- **IRIs are checked.** An IRI needs a scheme and must not contain whitespace or `<>"{}|^`\`. rdflib only warns about these characters, but pyoxigraph rejects them. Checking up front means the in-memory store never accepts a triple that the real store would refuse.
- `as_tuple()` and `from_tuple()` convert to and from rdflib's `(s, p, o)` tuples.

**`Changeset`** is a frozen dataclass with these fields:

- `id`: a UUID, later the LDES member id (`urn:uuid:…`)
- `added`: `frozenset[Triple]`
- `removed`: `frozenset[Triple]`
- `author`: must not be empty
- `timestamp`: must be timezone-aware and is stored in UTC
- `source`: optional

`Changeset.create(...)` generates the id and the timestamp. The constructor is for rebuilding stored changesets. Both accept any iterable of triples.

- **An update is one changeset** that removes the old triple and adds the new one, so the history shows it as a single change.
- **A triple cannot be both added and removed.** Because of that, the order in which a store applies the two parts does not change the result.
- **An empty changeset is valid** (`is_empty`). Whether it is recorded in the history is decided in #19.

## Consequences

- One model is shared by every store and by the API layer. The type checks give clear errors instead of corrupt data.
- **Literal normalisation.** rdflib normalises some typed literals by default, for example `"01"^^xsd:integer` becomes `"1"`. pyoxigraph keeps the original form. As long as all data passes through rdflib terms, both stores see the same value. The original form of such literals is lost, though. We accept that for now and leave rdflib's global setting alone.
- **No blank nodes, named graphs or quads yet.** Each can be added later without changing the existing fields.
