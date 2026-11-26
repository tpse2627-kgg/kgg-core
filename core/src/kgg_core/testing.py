"""Shared contract tests for :class:`~kgg_core.store.GraphStore` implementations.

Every store must pass the same tests, so kgg-core and kgg-django agree on what
a store does. To test a store, mix :class:`GraphStoreContract` into a
:class:`unittest.TestCase` (or a Django ``SimpleTestCase``/``TestCase``) and
implement :meth:`~GraphStoreContract.make_store`::

    class InMemoryGraphStoreTest(GraphStoreContract, unittest.TestCase):
        def make_store(self):
            return InMemoryGraphStore()

pytest and Django's test runner both pick the tests up. Each test calls
``make_store()`` once and expects a new, empty store.
"""

from __future__ import annotations

from abc import abstractmethod

from rdflib import Literal, URIRef

from kgg_core.model import Changeset, Triple
from kgg_core.store import GraphStore

__all__ = ["GraphStoreContract"]

_EX = "http://example.org/"
_XSD = "http://www.w3.org/2001/XMLSchema#"

ALICE = URIRef(_EX + "alice")
BOB = URIRef(_EX + "bob")
CAROL = URIRef(_EX + "carol")
KNOWS = URIRef(_EX + "knows")
NAME = URIRef(_EX + "name")
AGE = URIRef(_EX + "age")

ALICE_KNOWS_BOB = Triple(ALICE, KNOWS, BOB)
ALICE_KNOWS_CAROL = Triple(ALICE, KNOWS, CAROL)
BOB_KNOWS_CAROL = Triple(BOB, KNOWS, CAROL)
ALICE_NAME = Triple(ALICE, NAME, Literal("Alice", lang="en"))
ALICE_AGE = Triple(ALICE, AGE, Literal("42", datatype=URIRef(_XSD + "integer")))

ALL = {ALICE_KNOWS_BOB, ALICE_KNOWS_CAROL, BOB_KNOWS_CAROL, ALICE_NAME, ALICE_AGE}


class GraphStoreContract:
    """Tests every :class:`~kgg_core.store.GraphStore` must pass.

    Meant to be mixed into a ``unittest.TestCase``; it uses its ``assert*``
    methods. The name does not start with ``Test`` so pytest does not collect
    the mixin on its own.
    """

    @abstractmethod
    def make_store(self) -> GraphStore:
        """Return a new, empty store of the implementation under test."""

    def filled_store(self) -> GraphStore:
        store = self.make_store()
        store.add(ALL)
        return store

    # --- add, remove, len, contains ------------------------------------

    def test_new_store_is_empty(self):
        store = self.make_store()
        self.assertEqual(len(store), 0)
        self.assertEqual(list(store.triples()), [])
        self.assertNotIn(ALICE_KNOWS_BOB, store)

    def test_add_returns_number_of_new_triples(self):
        store = self.make_store()
        self.assertEqual(store.add([ALICE_KNOWS_BOB, BOB_KNOWS_CAROL]), 2)
        self.assertEqual(len(store), 2)
        self.assertIn(ALICE_KNOWS_BOB, store)
        self.assertIn(BOB_KNOWS_CAROL, store)

    def test_adding_a_duplicate_changes_nothing(self):
        store = self.make_store()
        store.add([ALICE_KNOWS_BOB])
        self.assertEqual(store.add([ALICE_KNOWS_BOB]), 0)
        self.assertEqual(store.add([ALICE_KNOWS_CAROL, ALICE_KNOWS_CAROL]), 1)
        self.assertEqual(len(store), 2)

    def test_add_nothing(self):
        store = self.make_store()
        self.assertEqual(store.add([]), 0)
        self.assertEqual(len(store), 0)

    def test_add_accepts_a_generator(self):
        store = self.make_store()
        self.assertEqual(store.add(t for t in ALL), len(ALL))

    def test_remove_returns_number_of_removed_triples(self):
        store = self.filled_store()
        self.assertEqual(store.remove([ALICE_KNOWS_BOB, ALICE_NAME]), 2)
        self.assertEqual(len(store), len(ALL) - 2)
        self.assertNotIn(ALICE_KNOWS_BOB, store)
        self.assertNotIn(ALICE_NAME, store)

    def test_removing_a_missing_triple_changes_nothing(self):
        store = self.make_store()
        store.add([ALICE_KNOWS_BOB])
        self.assertEqual(store.remove([BOB_KNOWS_CAROL]), 0)
        self.assertEqual(store.remove([ALICE_KNOWS_BOB, BOB_KNOWS_CAROL]), 1)
        self.assertEqual(store.remove([ALICE_KNOWS_BOB]), 0)
        self.assertEqual(len(store), 0)

    def test_only_triples_are_accepted(self):
        store = self.make_store()
        with self.assertRaises(TypeError):
            store.add([(ALICE, KNOWS, BOB)])
        with self.assertRaises(TypeError):
            store.remove([(ALICE, KNOWS, BOB)])
        self.assertEqual(len(store), 0)
        self.assertNotIn((ALICE, KNOWS, BOB), store)

    # --- pattern queries -----------------------------------------------

    def assertMatches(self, store, expected, **pattern):
        self.assertEqual(set(store.triples(**pattern)), set(expected), pattern)

    def test_triples_without_pattern_returns_everything(self):
        self.assertMatches(self.filled_store(), ALL)

    def test_triples_by_single_term(self):
        store = self.filled_store()
        self.assertMatches(
            store, {ALICE_KNOWS_BOB, ALICE_KNOWS_CAROL, ALICE_NAME, ALICE_AGE}, subject=ALICE
        )
        self.assertMatches(
            store, {ALICE_KNOWS_BOB, ALICE_KNOWS_CAROL, BOB_KNOWS_CAROL}, predicate=KNOWS
        )
        self.assertMatches(store, {ALICE_KNOWS_CAROL, BOB_KNOWS_CAROL}, object=CAROL)

    def test_triples_by_several_terms(self):
        store = self.filled_store()
        self.assertMatches(
            store, {ALICE_KNOWS_BOB, ALICE_KNOWS_CAROL}, subject=ALICE, predicate=KNOWS
        )
        self.assertMatches(store, {BOB_KNOWS_CAROL}, subject=BOB, object=CAROL)
        self.assertMatches(store, {ALICE_KNOWS_BOB}, subject=ALICE, predicate=KNOWS, object=BOB)

    def test_triples_without_match(self):
        store = self.filled_store()
        self.assertMatches(store, set(), subject=CAROL)
        self.assertMatches(store, set(), subject=BOB, object=BOB)

    def test_triples_by_literal_object(self):
        store = self.filled_store()
        self.assertMatches(store, {ALICE_NAME}, object=Literal("Alice", lang="en"))
        self.assertMatches(store, set(), object=Literal("Alice"))
        self.assertMatches(store, set(), object=Literal("Alice", lang="de"))

    def test_literals_round_trip(self):
        # rdflib normalises "042"^^xsd:integer to "42" and compares language
        # tags case-insensitively; a store must not break that, or a triple
        # read back would not match the one that was added.
        store = self.make_store()
        integer = URIRef(_XSD + "integer")
        odd_number = Triple(ALICE, AGE, Literal("042", datatype=integer))
        odd_lang = Triple(ALICE, NAME, Literal("Alice", lang="EN"))
        store.add([odd_number, odd_lang])
        self.assertIn(Triple(ALICE, AGE, Literal("42", datatype=integer)), store)
        self.assertIn(Triple(ALICE, NAME, Literal("Alice", lang="en")), store)
        self.assertEqual(set(store.triples()), {odd_number, odd_lang})
        self.assertEqual(store.remove(list(store.triples())), 2)

    # --- writing while reading -----------------------------------------

    def test_remove_while_iterating(self):
        store = self.filled_store()
        self.assertEqual(store.remove(store.triples(subject=ALICE)), 4)
        self.assertEqual(set(store.triples()), {BOB_KNOWS_CAROL})

    def test_write_inside_a_loop_over_triples(self):
        store = self.filled_store()
        for triple in store.triples(predicate=KNOWS):
            store.remove([triple])
            store.add([Triple(triple.object, KNOWS, triple.subject)])
        self.assertMatches(
            store,
            {Triple(BOB, KNOWS, ALICE), Triple(CAROL, KNOWS, ALICE), Triple(CAROL, KNOWS, BOB)},
            predicate=KNOWS,
        )

    # --- apply ---------------------------------------------------------

    def test_apply_adds_and_removes(self):
        store = self.make_store()
        store.add([ALICE_KNOWS_BOB])
        changeset = Changeset.create(
            added=[ALICE_KNOWS_CAROL], removed=[ALICE_KNOWS_BOB], author="test"
        )
        effective = store.apply(changeset)
        self.assertEqual(set(store.triples()), {ALICE_KNOWS_CAROL})
        self.assertEqual(effective, changeset)

    def test_apply_returns_only_what_changed(self):
        store = self.make_store()
        store.add([ALICE_KNOWS_BOB])
        changeset = Changeset.create(
            added=[ALICE_KNOWS_BOB, ALICE_NAME],
            removed=[BOB_KNOWS_CAROL],
            author="test",
            source="unit test",
        )
        effective = store.apply(changeset)
        self.assertEqual(effective.added, {ALICE_NAME})
        self.assertEqual(effective.removed, frozenset())
        self.assertEqual(
            (effective.id, effective.author, effective.timestamp, effective.source),
            (changeset.id, changeset.author, changeset.timestamp, changeset.source),
        )
        self.assertEqual(set(store.triples()), {ALICE_KNOWS_BOB, ALICE_NAME})

    def test_apply_without_effect_returns_an_empty_changeset(self):
        store = self.filled_store()
        nothing = store.apply(Changeset.create(added=[ALICE_KNOWS_BOB], author="test"))
        self.assertTrue(nothing.is_empty)
        self.assertTrue(store.apply(Changeset.create(author="test")).is_empty)
        self.assertEqual(set(store.triples()), ALL)
