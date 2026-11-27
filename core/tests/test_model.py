import uuid
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone

import pytest
from rdflib import BNode, Literal, URIRef

from kgg_core import Changeset, Triple

EX = "http://example.org/"
XSD_INTEGER = URIRef("http://www.w3.org/2001/XMLSchema#integer")
ALICE = URIRef(EX + "alice")
BOB = URIRef(EX + "bob")
KNOWS = URIRef(EX + "knows")
NAME = URIRef(EX + "name")


def knows(a=ALICE, b=BOB):
    return Triple(a, KNOWS, b)


# --- Triple -----------------------------------------------------------------


def test_triple_with_iri_and_literal_objects():
    assert knows().object == BOB
    assert Triple(ALICE, NAME, Literal("Alice", lang="en")).object.language == "en"


def test_triple_is_immutable():
    with pytest.raises(FrozenInstanceError):
        knows().subject = BOB


def test_equal_triples_are_equal_and_hash_the_same():
    assert knows() == knows()
    assert len({knows(), knows(), knows(BOB, ALICE)}) == 2


def test_literals_with_different_datatypes_are_different_triples():
    plain = Triple(ALICE, NAME, Literal("1"))
    typed = Triple(ALICE, NAME, Literal("1", datatype=XSD_INTEGER))
    assert plain != typed


@pytest.mark.parametrize(
    ("subject", "predicate", "obj"),
    [
        (BNode(), KNOWS, BOB),
        (Literal("alice"), KNOWS, BOB),
        ("http://example.org/alice", KNOWS, BOB),
        (ALICE, BNode(), BOB),
        (ALICE, Literal("knows"), BOB),
        (ALICE, KNOWS, BNode()),
        (ALICE, KNOWS, "bob"),
        (ALICE, KNOWS, None),
    ],
)
def test_triple_rejects_wrong_term_types(subject, predicate, obj):
    with pytest.raises(TypeError):
        Triple(subject, predicate, obj)


@pytest.mark.parametrize(
    "iri",
    ["alice", "http://example.org/a b", "http://example.org/<a>", "", "http://example.org/a\nb"],
)
def test_triple_rejects_invalid_iris(iri):
    with pytest.raises(ValueError):
        Triple(URIRef(iri), KNOWS, BOB)
    with pytest.raises(ValueError):
        Triple(ALICE, KNOWS, URIRef(iri))


def test_triple_accepts_non_http_iris():
    Triple(URIRef("urn:uuid:" + str(uuid.uuid4())), KNOWS, URIRef("mailto:bob@example.org"))


def test_tuple_round_trip():
    triple = knows()
    assert triple.as_tuple() == (ALICE, KNOWS, BOB)
    assert Triple.from_tuple(triple.as_tuple()) == triple


def test_n3():
    assert knows().n3() == f"<{EX}alice> <{EX}knows> <{EX}bob> ."


# --- Changeset --------------------------------------------------------------


def test_create_fills_id_and_utc_timestamp():
    before = datetime.now(UTC)
    changeset = Changeset.create(added=[knows()], author="mahdi", source="test")
    assert isinstance(changeset.id, uuid.UUID)
    assert before <= changeset.timestamp <= datetime.now(UTC)
    assert changeset.timestamp.utcoffset() == timedelta(0)
    assert changeset.added == frozenset({knows()})
    assert changeset.removed == frozenset()
    assert changeset.source == "test"


def test_create_gives_unique_ids():
    assert Changeset.create(author="a").id != Changeset.create(author="a").id


def test_create_accepts_any_iterable_and_drops_duplicates():
    changeset = Changeset.create(added=(t for t in [knows(), knows()]), author="a")
    assert changeset.added == frozenset({knows()})


def test_update_is_one_changeset():
    old, new = knows(), knows(ALICE, ALICE)
    changeset = Changeset.create(removed=[old], added=[new], author="a")
    assert changeset.removed == {old}
    assert changeset.added == {new}


def test_empty_changeset_is_valid():
    assert Changeset.create(author="a").is_empty
    assert not Changeset.create(added=[knows()], author="a").is_empty
    assert not Changeset.create(removed=[knows()], author="a").is_empty


def test_triple_cannot_be_added_and_removed():
    with pytest.raises(ValueError, match="both added and removed"):
        Changeset.create(added=[knows()], removed=[knows()], author="a")


@pytest.mark.parametrize("author", ["", "   "])
def test_author_is_required(author):
    with pytest.raises(ValueError):
        Changeset.create(author=author)


def test_changeset_only_contains_triples():
    with pytest.raises(TypeError):
        Changeset.create(added=[(ALICE, KNOWS, BOB)], author="a")


def test_constructor_rebuilds_a_stored_changeset_in_utc():
    berlin = timezone(timedelta(hours=1))
    stamp = datetime(2026, 11, 26, 22, 0, tzinfo=berlin)
    changeset_id = uuid.uuid4()
    changeset = Changeset(changeset_id, [knows()], [], "a", stamp)
    assert changeset.id == changeset_id
    assert changeset.added == frozenset({knows()})
    assert changeset.timestamp == stamp
    assert changeset.timestamp.tzinfo == UTC
    assert changeset.source is None


def test_naive_timestamp_is_rejected():
    with pytest.raises(ValueError, match="timezone"):
        Changeset(uuid.uuid4(), [], [], "a", datetime(2026, 11, 26, 22, 0))


def test_id_must_be_a_uuid():
    with pytest.raises(TypeError):
        Changeset(str(uuid.uuid4()), [], [], "a", datetime.now(UTC))


def test_changeset_is_immutable_and_hashable():
    changeset = Changeset.create(added=[knows()], author="a")
    with pytest.raises(FrozenInstanceError):
        changeset.author = "b"
    assert changeset in {changeset}


@pytest.mark.parametrize(
    ("author", "timestamp"),
    [(None, datetime.now(UTC)), (42, datetime.now(UTC)), ("a", "2026-11-26"), ("a", None)],
)
def test_author_and_timestamp_types_are_checked(author, timestamp):
    with pytest.raises(TypeError):
        Changeset(uuid.uuid4(), [], [], author, timestamp)
