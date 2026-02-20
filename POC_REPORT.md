# POC Report: Accelerating DB-Heavy FastAPI Tests with pytest-xdist

## Executive Summary
This proof of concept successfully demonstrates a mechanism to significantly reduce the runtime of database-bound test suites in FastAPI applications. By utilizing `pytest-xdist` and PostgreSQL's native `TEMPLATE` cloning, we achieved a **3.3x speedup** on a suite of 301 tests while maintaining absolute database isolation.

---

## Technical Architecture

### 1. Database Provisioning Strategy
The core of the speedup lies in how databases are handled for parallel workers:
*   **Template Database**: A single template database (`test_tpl_<uid>`) is created at the start of the test run. The SQLAlchemy schema is applied here once.
*   **Worker Cloning**: Each xdist worker (e.g., `gw0`, `gw1`) clones this template using:
    ```sql
    CREATE DATABASE test_worker_n TEMPLATE test_tpl_uid;
    ```
    Cloning is significantly faster than re-running schema migrations for every worker.
*   **Isolation**: Every worker operates on its own physical database, eliminating "deadlocks" or "dirty data" collisions between parallel tests.

### 2. Synchronization and Safety
*   **FileLock**: Used to coordinate workers during session setup. Only the first worker builds the template; all others wait until the template is ready before cloning.
*   **NullPool Connection Management**: SQLAlchemy's `NullPool` was implemented in the test engine to prevent connection leaking/sharing issues across the different event loops created by `pytest-asyncio` session and function fixtures.
*   **Auto-Cleanup**: After each test, tables are truncated (`TRUNCATE ... RESTART IDENTITY CASCADE`) to ensure function-level isolation.

---

## Performance Benchmarks

The benchmark was performed on a suite of **301 integration tests** (simulating heavy POST/GET API operations).

| Mode | Real Time (Seconds) | Tests per Second | Speedup |
| :--- | :--- | :--- | :--- |
| **Serial (Single Worker)** | 23.65s | ~12.7 | 1x (Baseline) |
| **Parallel (4 Workers)** | 9.06s | ~33.2 | 2.6x |
| **Parallel (Auto/All Cores)** | **7.05s** | **~42.7** | **3.3x** |

### Observation
As the test suite grows, the **setup cost** (cloning DBs) becomes negligible compared to the **execution gain**. In this POC, we moved from 23 seconds down to 7 seconds—a **~70% reduction** in developer wait time.

---

## Key Implementation Details

1.  **FastAPI Dependency Overrides**: The app's `get_session` is dynamically swapped in `conftest.py` to point to the worker-specific connection string.
2.  **Docker Integration**: Uses a containerized PostgreSQL instance for consistent performance and easy cleanup.
3.  **Lifespan Management**: `asgi-lifespan` was required to ensure FastAPI startup/shutdown events trigger correctly within the `httpx` async transport.

## Conclusion
The "Database-per-Worker" architecture is a production-ready pattern for scaling integration tests. It removes the bottleneck of sequential DB access without sacrificing the reliability of testing against a real database instance.
