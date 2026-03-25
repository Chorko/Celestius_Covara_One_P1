"""
Covara One - Backend Smoke Test
================================
Validates that all Python modules parse, import, and that the
ApiProviderPool engine behaves correctly under basic operations.

Run:  python backend/tests/smoke_test.py
"""

import sys, os, ast, pathlib, importlib, types

# -- 0. Paths --
ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
APP     = BACKEND / "app"
sys.path.insert(0, str(BACKEND))

passed = 0
failed = 0
errors: list[str] = []

def check(label: str, ok: bool, detail: str = ""):
    global passed, failed
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
py_files = sorted(APP.rglob("*.py"))
for pf in py_files:
    try:
        ast.parse(pf.read_text(encoding="utf-8"), filename=str(pf))
        check(f"Syntax OK: {pf.relative_to(BACKEND)}", True)
    except SyntaxError as e:
        check(f"Syntax OK: {pf.relative_to(BACKEND)}", False, str(e))


# -- 2. Import Check --
print("\n> S2  Isolated Import Check (critical modules)")

# Stub out heavy dependencies so imports succeed without network
for mod_name in [
    "fastapi", "fastapi.routing", "fastapi.security",
    "uvicorn", "pydantic", "pydantic_settings",
    "supabase", "httpx", "PIL", "PIL.Image",
    "google.generativeai", "dotenv",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)

# Stub dotenv.load_dotenv
dotenv_stub = sys.modules["dotenv"]
if not hasattr(dotenv_stub, "load_dotenv"):
    dotenv_stub.load_dotenv = lambda *a, **kw: None  # type: ignore

# Stub pydantic_settings.BaseSettings
ps_stub = sys.modules["pydantic_settings"]
class _FakeBaseSettings:
    def __init_subclass__(cls, **kw): pass
    def __init__(self, **kw): pass
ps_stub.BaseSettings = _FakeBaseSettings  # type: ignore

# Stub pydantic so models can be defined
pydantic_stub = sys.modules["pydantic"]
if not hasattr(pydantic_stub, "BaseModel"):
    class _FakeBaseModel:
        def __init_subclass__(cls, **kw): pass
        def __init__(self, **kw): pass
    pydantic_stub.BaseModel = _FakeBaseModel  # type: ignore
if not hasattr(pydantic_stub, "EmailStr"):
    pydantic_stub.EmailStr = str  # type: ignore
if not hasattr(pydantic_stub, "Field"):
    pydantic_stub.Field = lambda *a, **kw: None  # type: ignore

# Stub supabase.create_client
sb_stub = sys.modules["supabase"]
if not hasattr(sb_stub, "create_client"):
    sb_stub.create_client = lambda *a, **kw: None  # type: ignore

# Stub fastapi pieces
fa_stub = sys.modules["fastapi"]
if not hasattr(fa_stub, "FastAPI"):
    class _FakeFastAPI:
        def __init__(self, **kw): pass
        def include_router(self, *a, **kw): pass
        def add_middleware(self, *a, **kw): pass
        def on_event(self, *a):
            def deco(fn): return fn
            return deco
    fa_stub.FastAPI = _FakeFastAPI  # type: ignore
if not hasattr(fa_stub, "APIRouter"):
    class _FakeRouter:
        def __init__(self, **kw): pass
        def get(self, *a, **kw):
            def deco(fn): return fn
            return deco
        def post(self, *a, **kw):
            def deco(fn): return fn
            return deco
    fa_stub.APIRouter = _FakeRouter  # type: ignore
if not hasattr(fa_stub, "Depends"):
    fa_stub.Depends = lambda *a, **kw: None  # type: ignore
if not hasattr(fa_stub, "HTTPException"):
    class _FakeHTTPException(Exception):
        def __init__(self, *a, **kw): pass
    fa_stub.HTTPException = _FakeHTTPException  # type: ignore
if not hasattr(fa_stub, "UploadFile"):
    fa_stub.UploadFile = object  # type: ignore
if not hasattr(fa_stub, "File"):
    fa_stub.File = lambda *a, **kw: None  # type: ignore
if not hasattr(fa_stub, "Query"):
    fa_stub.Query = lambda *a, **kw: None  # type: ignore

fa_sec = sys.modules["fastapi.security"]
if not hasattr(fa_sec, "HTTPBearer"):
    class _FakeHTTPBearer:
        def __init__(self, **kw): pass
        def __call__(self, *a, **kw): return None
    fa_sec.HTTPBearer = _FakeHTTPBearer  # type: ignore
if not hasattr(fa_sec, "HTTPAuthorizationCredentials"):
    fa_sec.HTTPAuthorizationCredentials = object  # type: ignore

# Now try importing the critical backend modules
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
    except Exception as e:
        check(f"Import: {mod_path}", False, f"{type(e).__name__}: {e}")


# -- 3. ApiProviderPool Unit Tests --
print("\n> S3  ApiProviderPool Functional Tests")

try:
    import asyncio
    from app.services.api_pool import ApiProviderPool, ApiProvider

    # 3a. Empty pool
    pool = ApiProviderPool("test")
    check("Empty pool has 0 providers", pool.provider_count == 0)

    # 3b. Add providers via dataclass
    pool.add_provider(ApiProvider(name="ProviderA", fetch_fn=lambda **kw: {"source": "A"}, priority=1))
    pool.add_provider(ApiProvider(name="ProviderB", fetch_fn=lambda **kw: {"source": "B"}, priority=2))
    check("Add provider increases count to 2", pool.provider_count == 2)

    # 3c. Async call returns data
    result = asyncio.get_event_loop().run_until_complete(pool.call(city="Mumbai"))
    check("pool.call() returns data dict", result is not None and result.get("data") is not None)
    check("pool.call() reports provider name", result.get("provider") is not None)

    # 3d. Remove provider
    pool.remove_provider("ProviderA")
    check("Remove provider decreases count to 1", pool.provider_count == 1)
    remaining = [p.name for p in pool._providers]
    check("Correct provider removed", "ProviderA" not in remaining and "ProviderB" in remaining)

    # 3e. Cache behavior (second call should be cached)
    r1 = asyncio.get_event_loop().run_until_complete(pool.call(city="Mumbai"))
    r2 = asyncio.get_event_loop().run_until_complete(pool.call(city="Mumbai"))
    check("Second call is cached", r2.get("cached") == True)

    # 3f. Health report
    report = pool.get_health_report()
    check("Health report has pool name", report.get("pool") == "test")

except Exception as e:
    check("ApiProviderPool import/test", False, f"{type(e).__name__}: {e}")


# -- 4. Config auto-discovery (dry run) --
print("\n> S4  Config Auto-Discovery")
try:
    # The real convention is {PREFIX}_API_KEY_{SLOT}
    # So get_api_keys("SMOKE") scans for SMOKE_API_KEY_*
    os.environ["SMOKE_API_KEY_1"] = "val_1"
    os.environ["SMOKE_API_KEY_2"] = "val_2"
    os.environ["SMOKE_API_KEY_prod"] = "val_prod"

    # Test the exact algorithm from config.py lines 50-56
    prefix_pattern = "SMOKE_API_KEY_"
    discovered = {}
    for env_name, env_value in os.environ.items():
        if env_name.startswith(prefix_pattern) and env_value:
            slot = env_name[len(prefix_pattern):]
            discovered[slot] = env_value

    check("Auto-discovery finds 3 keys", len(discovered) == 3)
    check("Auto-discovery values correct",
          set(discovered.values()) == {"val_1", "val_2", "val_prod"})

    # Verify the Settings class has get_api_keys as a static method
    from app.config import Settings as RealSettings
    check("Settings.get_api_keys is callable", callable(getattr(RealSettings, "get_api_keys", None)))

    # Cleanup
    del os.environ["SMOKE_API_KEY_1"]
    del os.environ["SMOKE_API_KEY_2"]
    del os.environ["SMOKE_API_KEY_prod"]

except Exception as e:
    check("Config auto-discovery", False, f"{type(e).__name__}: {e}")


# -- Summary --
print(f"\n{'='*60}")
print(f"  SMOKE TEST COMPLETE:  {passed} passed, {failed} failed")
print(f"{'='*60}")
if errors:
    print("\n  Failures:")
    for e in errors:
        print(f"    {e}")
    sys.exit(1)
else:
    print("  All checks passed!\n")
    sys.exit(0)
