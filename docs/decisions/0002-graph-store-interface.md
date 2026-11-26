# 0002: GraphStore interface and in-memory store

**Status:** proposed · **Date:** 26.11.2026 · **Issue:** [#18](https://github.com/tpse2627-kgg/kgg-core/issues/18)

## Context

kgg-core needs to store triples without knowing where they live. Tests need a fast store with no setup. kgg-django (tpse2627-kgg/kgg-django#4) needs a persistent one on pyoxigraph. Both must behave the same, and every write must go through a changeset (#19) so the history and the LDES stream stay complete.

## Decision

`kgg_core/store.py` defines **`GraphStore`, an abstract base class**. A store behaves like a set of `Triple`s (one RDF graph):

| Method | Meaning |
|---|---|
| `add(triples) -> int` | add the triples and return how many were new |
| `remove(triples) -> int` | remove the triples and return how many were there |
| `triples(subject=None, predicate=None, object=None)` | iterate over the matching triples; `None` matches any term |
| `triple in store`, `len(store)` | membership and size |
| `apply(changeset) -> Changeset` | apply a changeset and return the **effective** changeset |

- **Adding a duplicate or removing a missing triple is not an error.** It just changes nothing. That keeps writes idempotent.
- **`apply` is a concrete method on the base class.** It removes, then adds, and returns a copy of the changeset that holds only the triples that really changed, with the same id, author, timestamp and source. #19 records that effective changeset in the history, so the history and LDES show what really happened. A store with transactions (pyoxigraph) should override `apply` to make it atomic. Because it is in the interface from the start, adding atomicity later doesn't change any callers.
- **Writing while reading is allowed.** `store.remove(store.triples(subject=s))` must work, so `add`/`remove` read their input first and `triples()` may return a snapshot.
- **The pattern query maps one to one onto pyoxigraph's `quads_for_pattern`**, using the default graph.
- **An ABC rather than a `Protocol`**, because a store that misses a method fails when it is created, not later at a call site, and `apply` can be shared.

**`InMemoryGraphStore`** keeps the triples in a Python `set` and answers queries by scanning them. It's small, obviously correct and fast enough for tests and the minimum scope.

**`kgg_core.testing.GraphStoreContract`** holds the tests every store must pass, as a mixin for `unittest.TestCase`. kgg-core runs it against the in-memory store. kgg-django mixes it into a Django test case with a temporary pyoxigraph store, so both stores are checked against the same rules. A throwaway pyoxigraph adapter passed the contract while we wrote it.

## Consequences

- Swapping the store doesn't change the core logic, and kgg-core stays free of Django and pyoxigraph.
- `apply` in the base class is not atomic. If a store fails between removing and adding, the graph is half changed. That's acceptable for the in-memory store; the pyoxigraph store must override it.
- No SPARQL, named graphs or transactions in the interface yet. They can be added when the REST API or LDES needs them.
