import os
import pytest
from filelock import FileLock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text, NullPool
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager

from app.main import app
from app.models import Base
from app.deps import get_session

ADMIN_DB_URL = os.getenv("ADMIN_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres")
BASE_DB_URL_TEMPLATE = os.getenv("BASE_DB_URL_TEMPLATE", "postgresql+asyncpg://postgres:postgres@localhost:5432/{db_name}")

@pytest.fixture(scope="session")
def worker_id_custom(worker_id):
    """Normalize worker_id even when xdist is not used."""
    return worker_id if worker_id != "master" else "gw0"

@pytest.fixture(scope="session")
def worker_identity(worker_id_custom, testrun_uid):
    uid = testrun_uid or "local"
    tpl_name = f"test_tpl_{uid}"
    worker_name = f"test_{uid}_{worker_id_custom}"
    return {
        "uid": uid,
        "worker_id": worker_id_custom,
        "tpl_name": tpl_name,
        "worker_name": worker_name
    }

@pytest.fixture(scope="session")
def shared_tmp_dir(tmp_path_factory):
    # In xdist, tmp_path_factory base is shared across workers
    # We use this to store the lock file
    return tmp_path_factory.getbasetemp().parent

@pytest.fixture(scope="session", autouse=True)
async def ensure_template_db(worker_identity, shared_tmp_dir):
    tpl_name = worker_identity["tpl_name"]
    lock_file = shared_tmp_dir / f"{tpl_name}.lock"
    
    with FileLock(str(lock_file)):
        admin_engine = create_async_engine(ADMIN_DB_URL, isolation_level="AUTOCOMMIT")
        async with admin_engine.connect() as conn:
            res = await conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname='{tpl_name}'"))
            exists = res.scalar()
            
            if not exists:
                print(f"[Worker {worker_identity['worker_id']}] Creating template DB {tpl_name}")
                await conn.execute(text(f"CREATE DATABASE {tpl_name}"))
        
        await admin_engine.dispose()
        
        tpl_db_url = BASE_DB_URL_TEMPLATE.format(db_name=tpl_name)
        tpl_engine = create_async_engine(tpl_db_url)
        
        async with tpl_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        await tpl_engine.dispose()

@pytest.fixture(scope="session")
async def ensure_worker_db(worker_identity, ensure_template_db):
    tpl_name = worker_identity["tpl_name"]
    worker_name = worker_identity["worker_name"]
    
    admin_engine = create_async_engine(ADMIN_DB_URL, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        res = await conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname='{worker_name}'"))
        exists = res.scalar()
        if exists:
            print(f"[Worker {worker_identity['worker_id']}] Dropping existing worker DB {worker_name}")
            try:
                await conn.execute(text(f"DROP DATABASE {worker_name} WITH (FORCE)"))
            except Exception:
                await conn.execute(text(f"DROP DATABASE {worker_name}"))
            
        print(f"[Worker {worker_identity['worker_id']}] Creating worker DB {worker_name} FROM {tpl_name}")
        await conn.execute(text(f"CREATE DATABASE {worker_name} TEMPLATE {tpl_name}"))
        
    await admin_engine.dispose()
    
    worker_db_url = BASE_DB_URL_TEMPLATE.format(db_name=worker_name)
    yield worker_db_url
    
    # Teardown: Drop worker DB
    admin_engine = create_async_engine(ADMIN_DB_URL, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        print(f"[Worker {worker_identity['worker_id']}] Dropping worker DB {worker_name}")
        try:
            await conn.execute(text(f"DROP DATABASE {worker_name} WITH (FORCE)"))
        except Exception:
            await conn.execute(text(f"DROP DATABASE {worker_name}"))
    await admin_engine.dispose()

@pytest.fixture(scope="session")
async def async_engine(ensure_worker_db):
    engine = create_async_engine(ensure_worker_db, poolclass=NullPool)
    yield engine
    await engine.dispose()

@pytest.fixture(scope="session")
def async_session_factory(async_engine):
    return async_sessionmaker(async_engine, expire_on_commit=False, autoflush=False)

@pytest.fixture(scope="function", autouse=True)
async def clean_db(async_engine):
    yield
    # Truncate tables after test
    async with async_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f"TRUNCATE TABLE {table.name} RESTART IDENTITY CASCADE"))

@pytest.fixture(scope="function")
def app_with_test_deps(async_session_factory):
    async def override_get_session():
        async with async_session_factory() as session:
            yield session
            
    app.dependency_overrides[get_session] = override_get_session
    yield app
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
async def client(app_with_test_deps):
    async with LifespanManager(app_with_test_deps):
        transport = ASGITransport(app=app_with_test_deps)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
