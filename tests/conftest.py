import os
import sys
import time
import tracemalloc
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastapi_service import Container


@pytest.fixture
def container():
    c = Container()
    yield c
    c.clear()


@pytest.fixture
def app():
    return FastAPI()


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture(scope="session")
def load_factor():
    value = os.getenv("TEST_LOAD_FACTOR", "25")
    try:
        return int(value)
    except Exception:
        return 25


@pytest.fixture
def perf_monitor():
    tracemalloc.start()
    start = time.perf_counter()
    yield
    tracemalloc.stop()
    end = time.perf_counter()
    return end - start
