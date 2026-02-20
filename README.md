# FastAPI + Pytest-xdist + PostgreSQL POC

This is a proof of concept demonstrating how to speed up a DB-heavy pytest suite using `pytest-xdist`. Each xdist worker gets its own cloned PostgreSQL database, allowing fully isolated parallel test execution.

## Stack
- FastAPI
- SQLAlchemy 2.x async ORM
- PostgreSQL (asyncpg)
- Pytest + pytest-xdist + pytest-asyncio
- HTTPX AsyncClient

## Setup

1. Have a running PostgreSQL instance with an admin user. The app assumes `postgres:postgres@localhost:5432/postgres`.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` if you need custom connections:
   ```bash
   cp .env.example .env
   ```

## Performance Results

A benchmark run with **301 integration tests** yielded:
- **Serial Baseline**: 23.65s
- **Parallel (Auto Workers)**: **7.05s** (3.3x faster / ~70% reduction)

For a detailed analysis, check out the [Full POC Report](POC_REPORT.md).

## Running the Tests & Benchmark

You can run tests normally:
```bash
pytest -q
pytest -n auto --dist=loadscope
```

Or just run the included benchmark script that measures the time difference:
```bash
bash scripts/benchmark.sh
```

## How It Works
- **conftest.py**: Coordinates one template database per test test execution (`testrun_uid`).
- **FileLock**: Only allows the first worker to build the schema on the template DB.
- **Worker DB**: Each worker creates its own test DB copied from the template DB via `CREATE DATABASE ... TEMPLATE ...`.
- **Database Cleanup**: After every test, tables are truncated (`TRUNCATE TABLE ... RESTART IDENTITY CASCADE`).
- **FastAPI overrides**: The `get_session` dependency is overriden so that worker tests execute explicitly pointing to the cloned worker DB.

## Caveats Encountered
1. `asgi-lifespan` is needed with `httpx.AsyncClient` + `ASGITransport` to run app lifecycle events.
2. `DROP DATABASE (FORCE)` works smoothly on PG 13+, but must not be chained within an active transaction block so we set `isolation_level="AUTOCOMMIT"`.
3. Worker logging is helpful to visually inspect `test_<uid>_gw0` creation/dropping behavior.
4. With pytest-asyncio auto mode, ensuring `scope="session"` for fixtures matches up nicely. `pytest.mark.anyio` works easily by passing the `anyio_backend` fixture.
