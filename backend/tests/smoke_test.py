"""
Covara One - Backend Smoke Test
================================
Validates that all Python modules parse, import, and that the
ApiProviderPool engine behaves correctly under basic operations.

Run: python backend/tests/smoke_test.py
"""

import sys
import os
import ast
import pathlib
import importlib
import types


def run_smoke_test() -> int:
    # -- 0. Paths --
    root = pathlib.Path(__file__).resolve().parents[2]
    backend = root / "backend"
    app = backend / "app"
    sys.path.insert(0, str(backend))

    passed = 0
    failed = 0
    errors: list[str] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        nonlocal passed, failed
        if ok:
            passed += 1
            print(f"  [PASS] {label}")
        else:
            failed += 1
            msg = f"  [FAIL] {label}" + (f" -- {detail}" if detail else "")
            print(msg)
            errors.append(msg)

    # -- 1. AST Syntax Check --
    print("\n> S1  AST Syntax Check (all .py files under backend/app)")
    py_files = sorted(app.rglob("*.py"))
    for py_file in py_files:
        try:
            ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            check(f"Syntax OK: {py_file.relative_to(backend)}", True)
        except SyntaxError as exc:
            check(f"Syntax OK: {py_file.relative_to(backend)}", False, str(exc))

    # -- 2. Import Check --
    print("\n> S2  Isolated Import Check (critical modules)")

    # Stub heavy dependencies so imports succeed without network
    for mod_name in [
        "fastapi",
        "fastapi.routing",
        "fastapi.security",
        "uvicorn",
        "pydantic",
        "pydantic_settings",
        "supabase",
        "httpx",
        "PIL",
        "PIL.Image",
        "google.generativeai",
        "dotenv",
    ]:
        if mod_name not in sys.modules:
            sys.modules[mod_name] = types.ModuleType(mod_name)

    # Stub dotenv.load_dotenv
    dotenv_stub = sys.modules["dotenv"]
    if not hasattr(dotenv_stub, "load_dotenv"):
        dotenv_stub.load_dotenv = lambda *args, **kwargs: None  # type: ignore

    # Stub pydantic_settings.BaseSettings
    ps_stub = sys.modules["pydantic_settings"]

    class _FakeBaseSettings:
        def __init_subclass__(cls, **kwargs):
            pass

        def __init__(self, **kwargs):
            pass

    ps_stub.BaseSettings = _FakeBaseSettings  # type: ignore

    # Stub pydantic so models can be defined
    pydantic_stub = sys.modules["pydantic"]
    if not hasattr(pydantic_stub, "BaseModel"):

        class _FakeBaseModel:
            def __init_subclass__(cls, **kwargs):
                pass

            def __init__(self, **kwargs):
                pass

        pydantic_stub.BaseModel = _FakeBaseModel  # type: ignore
    if not hasattr(pydantic_stub, "EmailStr"):
        pydantic_stub.EmailStr = str  # type: ignore
    if not hasattr(pydantic_stub, "Field"):
        pydantic_stub.Field = lambda *args, **kwargs: None  # type: ignore

    # Stub supabase.create_client
    supabase_stub = sys.modules["supabase"]
    if not hasattr(supabase_stub, "create_client"):
        supabase_stub.create_client = lambda *args, **kwargs: None  # type: ignore

    # Stub fastapi pieces
    fastapi_stub = sys.modules["fastapi"]
    if not hasattr(fastapi_stub, "FastAPI"):

        class _FakeFastAPI:
            def __init__(self, **kwargs):
                pass

            def include_router(self, *args, **kwargs):
                pass

            def add_middleware(self, *args, **kwargs):
                pass

            def on_event(self, *args):
                def deco(fn):
                    return fn

                return deco

        fastapi_stub.FastAPI = _FakeFastAPI  # type: ignore

    if not hasattr(fastapi_stub, "APIRouter"):

        class _FakeRouter:
            def __init__(self, **kwargs):
                pass

            def get(self, *args, **kwargs):
                def deco(fn):
                    return fn

                return deco

            def post(self, *args, **kwargs):
                def deco(fn):
                    return fn

                return deco

        fastapi_stub.APIRouter = _FakeRouter  # type: ignore

    if not hasattr(fastapi_stub, "Depends"):
        fastapi_stub.Depends = lambda *args, **kwargs: None  # type: ignore

    if not hasattr(fastapi_stub, "HTTPException"):

        class _FakeHTTPException(Exception):
            def __init__(self, *args, **kwargs):
                pass

        fastapi_stub.HTTPException = _FakeHTTPException  # type: ignore

    if not hasattr(fastapi_stub, "UploadFile"):
        fastapi_stub.UploadFile = object  # type: ignore

    if not hasattr(fastapi_stub, "File"):
        fastapi_stub.File = lambda *args, **kwargs: None  # type: ignore

    if not hasattr(fastapi_stub, "Query"):
        fastapi_stub.Query = lambda *args, **kwargs: None  # type: ignore

    fastapi_sec_stub = sys.modules["fastapi.security"]
    if not hasattr(fastapi_sec_stub, "HTTPBearer"):

        class _FakeHTTPBearer:
            def __init__(self, **kwargs):
                pass

            def __call__(self, *args, **kwargs):
                return None

        fastapi_sec_stub.HTTPBearer = _FakeHTTPBearer  # type: ignore

    if not hasattr(fastapi_sec_stub, "HTTPAuthorizationCredentials"):
        fastapi_sec_stub.HTTPAuthorizationCredentials = object  # type: ignore

    # Try importing critical backend modules
    critical_modules = [
        "app.config",
        "app.services.api_pool",
        "app.services.weather_ingest",
        "app.services.aqi_ingest",
        "app.services.traffic_ingest",
    ]

    for mod_path in critical_modules:
        try:
            importlib.import_module(mod_path)
            check(f"Import: {mod_path}", True)
        except Exception as exc:
            check(f"Import: {mod_path}", False, f"{type(exc).__name__}: {exc}")

    # -- 3. ApiProviderPool Unit Tests --
    print("\n> S3  ApiProviderPool Functional Tests")

    try:
        import asyncio
        from app.services.api_pool import ApiProviderPool, ApiProvider

        pool = ApiProviderPool("test")
        check("Empty pool has 0 providers", pool.provider_count == 0)

        pool.add_provider(
            ApiProvider(name="ProviderA", fetch_fn=lambda **kwargs: {"source": "A"}, priority=1)
        )
        pool.add_provider(
            ApiProvider(name="ProviderB", fetch_fn=lambda **kwargs: {"source": "B"}, priority=2)
        )
        check("Add provider increases count to 2", pool.provider_count == 2)

        result = asyncio.get_event_loop().run_until_complete(pool.call(city="Mumbai"))
        check("pool.call() returns data dict", result is not None and result.get("data") is not None)
        check("pool.call() reports provider name", result.get("provider") is not None)

        pool.remove_provider("ProviderA")
        check("Remove provider decreases count to 1", pool.provider_count == 1)
        remaining = [provider.name for provider in pool._providers]
        check("Correct provider removed", "ProviderA" not in remaining and "ProviderB" in remaining)

        _ = asyncio.get_event_loop().run_until_complete(pool.call(city="Mumbai"))
        second = asyncio.get_event_loop().run_until_complete(pool.call(city="Mumbai"))
        check("Second call is cached", second.get("cached") is True)

        report = pool.get_health_report()
        check("Health report has pool name", report.get("pool") == "test")

    except Exception as exc:
        check("ApiProviderPool import/test", False, f"{type(exc).__name__}: {exc}")

    # -- 4. Config auto-discovery (dry run) --
    print("\n> S4  Config Auto-Discovery")
    try:
        os.environ["SMOKE_API_KEY_1"] = "val_1"
        os.environ["SMOKE_API_KEY_2"] = "val_2"
        os.environ["SMOKE_API_KEY_prod"] = "val_prod"

        prefix_pattern = "SMOKE_API_KEY_"
        discovered = {}
        for env_name, env_value in os.environ.items():
            if env_name.startswith(prefix_pattern) and env_value:
                slot = env_name[len(prefix_pattern):]
                discovered[slot] = env_value

        check("Auto-discovery finds 3 keys", len(discovered) == 3)
        check(
            "Auto-discovery values correct",
            set(discovered.values()) == {"val_1", "val_2", "val_prod"},
        )

        from app.config import Settings as RealSettings

        check(
            "Settings.get_api_keys is callable",
            callable(getattr(RealSettings, "get_api_keys", None)),
        )

        del os.environ["SMOKE_API_KEY_1"]
        del os.environ["SMOKE_API_KEY_2"]
        del os.environ["SMOKE_API_KEY_prod"]

    except Exception as exc:
        check("Config auto-discovery", False, f"{type(exc).__name__}: {exc}")

    # -- Summary --
    print(f"\n{'='*60}")
    print(f"  SMOKE TEST COMPLETE:  {passed} passed, {failed} failed")
    print(f"{'='*60}")

    if errors:
        print("\n  Failures:")
        for err in errors:
            print(f"    {err}")
        return 1

    print("  All checks passed!\n")
    return 0


def main() -> None:
    sys.exit(run_smoke_test())


if __name__ == "__main__":
    main()
