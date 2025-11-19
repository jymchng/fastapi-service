import time
import statistics
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_service import injectable, Depends, Scopes


def test_performance_response_times_under_load(load_factor):
    app = FastAPI()
    client = TestClient(app)

    @injectable(scope=Scopes.SINGLETON)
    class Work:
        def compute(self, x: int) -> int:
            return x * x

    @app.get("/work/{x}")
    def route(x: int, w: Work = Depends(Work)):
        return {"y": w.compute(x)}

    latencies = []
    for i in range(load_factor):
        t0 = time.perf_counter()
        r = client.get(f"/work/{i}")
        t1 = time.perf_counter()
        latencies.append(t1 - t0)
        assert r.status_code == 200

    p95 = statistics.quantiles(latencies, n=100)[94]
    assert p95 < 0.2


def test_performance_resource_utilization_memory_growth(load_factor):
    app = FastAPI()
    client = TestClient(app)

    @injectable
    class Payload:
        def build(self, n: int) -> dict:
            return {"v": [i for i in range(n)]}

    @app.get("/payload/{n}")
    def route(n: int, p: Payload = Depends(Payload)):
        return p.build(n)

    import tracemalloc

    tracemalloc.start()
    for i in range(load_factor):
        client.get(f"/payload/{i % 50}")
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert peak < 20 * 1024 * 1024


def test_performance_scalability_thresholds(load_factor):
    app = FastAPI()
    client = TestClient(app)

    @injectable
    class Counter:
        def __init__(self):
            self.c = 0

        def inc(self) -> int:
            self.c += 1
            return self.c

    @app.get("/count")
    def route(svc: Counter = Depends(Counter)):
        return {"c": svc.inc()}

    start = time.perf_counter()
    for _ in range(load_factor * 2):
        client.get("/count")
    duration = time.perf_counter() - start
    assert duration < 3.0
