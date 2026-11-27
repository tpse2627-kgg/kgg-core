import unittest

import pytest

from kgg_core import GraphStore, InMemoryGraphStore
from kgg_core.testing import ALICE_KNOWS_BOB, ALL, GraphStoreContract


class InMemoryGraphStoreTest(GraphStoreContract, unittest.TestCase):
    def make_store(self):
        return InMemoryGraphStore()


def test_in_memory_store_can_start_filled():
    store = InMemoryGraphStore(ALL)
    assert len(store) == len(ALL)
    assert repr(store) == f"InMemoryGraphStore({len(ALL)} triples)"


def test_triples_returns_an_iterator():
    store = InMemoryGraphStore([ALICE_KNOWS_BOB])
    result = store.triples()
    assert next(result) == ALICE_KNOWS_BOB
    assert next(result, None) is None


def test_graph_store_cannot_be_instantiated():
    with pytest.raises(TypeError):
        GraphStore()


def test_incomplete_store_cannot_be_instantiated():
    class OnlyAdd(GraphStore):
        def add(self, triples):
            return 0

    with pytest.raises(TypeError):
        OnlyAdd()
