from kgg_core import health


def test_health_returns_ok():
    assert health() == "ok"