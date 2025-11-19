# Test Suite for fastapi-service

## Setup

- Install dependencies using your preferred workflow. With Nox: `nox -s test`.
- Or run tests directly: `python -m pytest`.
- Environment variable `TEST_LOAD_FACTOR` controls performance test load (default: 100).

## Structure

- `unit/`: Core DI behaviors and edge cases.
- `integration/`: FastAPI endpoint interactions with DI.
- `security/`: Validation, authentication/authorization, data protection.
- `performance/`: Load, resource utilization, scalability.
- `benchmark.py`: Lightweight throughput benchmark aligned with existing Nox session.

## Expected Outcomes

- Unit tests validate correct resolution, scoping, auto-resolve, and error paths.
- Integration tests confirm DI works across path/query/header and async routes.
- Performance tests ensure p95 latency < 200ms, memory peak < 20MB, suite completes < 3s for configured load.
- Security tests ensure invalid inputs return errors, auth gates function, and secrets aren’t exposed.

## Running

- Run a single test: `python -m pytest tests/unit/test_injectable_basic.py::test_injectable_basic_resolution`.
- Run a suite: `python -m pytest tests/performance -m "not slow"`.

## Failure Analysis

- Inspect coverage: tests use `pytest-cov` to report missing lines.
- Check stack traces and assertion messages for failing modules.
- For performance regressions, review p95 latency and memory peaks; increase `TEST_LOAD_FACTOR` locally to reproduce.