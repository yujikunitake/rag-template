import os

import pytest


def test_database_get_engine_raises_without_url():
    from src.database import _get_engine

    _get_engine.cache_clear()
    saved = os.environ.pop("DATABASE_URL", None)
    try:
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            _get_engine()
    finally:
        if saved is not None:
            os.environ["DATABASE_URL"] = saved
        _get_engine.cache_clear()


def test_database_get_engine_returns_same_instance():
    from src.database import _get_engine

    _get_engine.cache_clear()
    assert _get_engine() is _get_engine()
