import time
import statistics
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_service import injectable, Depends


def test_benchmark_di_resolution_throughput():
    app = FastAPI()
    client = TestClient(app)

    @injectable
    class Calc:
        def mul(self, a: int, b: int) -> int:
            return a * b

    @app.get("/mul/{a}/{b}")
    def route(a: int, b: int, c: Calc = Depends(Calc)):
        return {"r": c.mul(a, b)}

    latencies = []
    for i in range(200):
        t0 = time.perf_counter()
        r = client.get(f"/mul/{i}/{i}")
        t1 = time.perf_counter()
        latencies.append(t1 - t0)
        assert r.status_code == 200

    mean_latency = statistics.mean(latencies)
    assert mean_latency < 0.02