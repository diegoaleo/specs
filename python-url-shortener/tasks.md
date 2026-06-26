# Implementation Plan: Python URL Shortener

## Overview

Implement a FastAPI-based URL shortener service with SQLite persistence via SQLAlchemy (async). The implementation proceeds bottom-up: project scaffolding and data model first, then the store layer, code generator, service layer, API routers, and finally integration wiring. Property-based tests (Hypothesis) and unit tests (pytest + pytest-asyncio) are placed close to the code they verify.

## Tasks

- [x] 1. Set up project structure, dependencies, and core domain model
  - Create the directory layout: `app/`, `app/api/`, `app/api/routers/`, `app/services/`, `app/store/`, `app/schemas/`, `tests/unit/`, `tests/unit/test_api/`, `tests/integration/`
  - Add `__init__.py` files to every package
  - Create `pyproject.toml` (or `requirements.txt`) pinning: `fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `aiosqlite`, `pydantic`, `hypothesis`, `pytest`, `pytest-asyncio`, `httpx`
  - Create `app/exceptions.py` defining the full exception hierarchy: `AppError`, `ValidationError`, `NotFoundError`, `ConflictError`, `ExpiredError`, `StorageError`, `StorageWriteError`, `CodeGenerationError`
  - Create `app/models.py` with the `Mapping` dataclass (`short_code`, `original_url`, `created_at`, `access_count`, `expires_at`) and its `is_expired()` method
  - _Requirements: 1.1, 2.1, 3.1, 5.1, 6.1_

- [x] 2. Implement Pydantic schemas
  - [x] 2.1 Create `app/schemas/__init__.py` and `app/schemas/url.py` with `ShortenRequest`, `ShortenResponse`, `StatsResponse`, and `HealthResponse`
    - `ShortenRequest.url` uses `AnyHttpUrl`; `custom_code` and `expires_in` are optional
    - `expires_in` validator: positive integer, ≤ 315,576,000
    - `custom_code` validator: alphanumeric + hyphens, length 3–50
    - _Requirements: 1.3, 1.4, 5.2, 5.4, 6.1, 6.4_

  - [-]* 2.2 Write unit tests for Pydantic schema validation
    - Valid request passes; missing `url` → 422; invalid scheme (`ftp://`) → 422; whitespace custom code → 422; `expires_in=0` → 422; `expires_in=315576001` → 422; custom code with special chars → 422; custom code 2 chars → 422; custom code 51 chars → 422
    - _Requirements: 1.3, 1.4, 5.2, 5.4, 6.4_

- [x] 3. Implement the store layer
  - [x] 3.1 Create `app/store/url_store.py` with the `URLStore` class
    - Define the SQLAlchemy `url_mappings` table (`short_code` PK, `original_url` with index, `created_at`, `access_count`, `expires_at`)
    - Implement `initialize()`: connect, verify reachability, create tables; raise `StorageError` on failure
    - Implement `find_by_original_url()`, `find_by_short_code()`, `create_mapping()`, `increment_access_count()`, `health_probe()`
    - `create_mapping()` raises `StorageWriteError` on DB write failure
    - `increment_access_count()` uses an atomic `UPDATE … SET access_count = access_count + 1`; logs warning on failure but does not raise (fire-and-forget)
    - `health_probe()` runs `SELECT 1` within the given timeout
    - _Requirements: 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 3.5, 7.1, 7.2_

  - [-]* 3.2 Write property test for persistence round-trip (Property 5)
    - **Property 5: Persistence round-trip**
    - Use an in-memory SQLite instance (`sqlite+aiosqlite:///:memory:`)
    - Generate arbitrary `Mapping` values (varied `short_code`, `original_url`, `created_at`, `access_count`, `expires_at`) with Hypothesis; write then read back and assert field equality
    - **Validates: Requirements 3.1, 3.4**

  - [-]* 3.3 Write unit tests for store layer
    - `initialize()` raises `StorageError` when DB is unreachable
    - `create_mapping()` raises `StorageWriteError` on write failure
    - `find_by_short_code()` returns `None` for unknown code
    - `find_by_original_url()` returns `None` for unknown URL
    - `increment_access_count()` is fire-and-forget (failure logged, no raise)
    - `health_probe()` returns `False` on timeout
    - _Requirements: 2.4, 3.3, 3.5_

- [x] 4. Implement the code generator
  - [x] 4.1 Create `app/services/code_generator.py` with the `CodeGenerator` class
    - `ALPHABET = string.ascii_letters + string.digits`
    - `generate(length=8)` uses `secrets.choice(ALPHABET)` for cryptographic randomness
    - Length parameter must be accepted in range 6–12
    - _Requirements: 1.5, 1.6_

  - [-]* 4.2 Write property test for short code generation correctness (Property 1)
    - **Property 1: Short code generation correctness**
    - For any length in 6–12, generate 100 codes and assert every character is in `ALPHABET` and the length matches
    - **Validates: Requirements 1.5, 1.7**

  - [-]* 4.3 Write unit tests for code generator
    - Default `generate()` returns an 8-character alphanumeric string
    - `generate(6)` and `generate(12)` respect length bounds
    - All characters in returned code are in `ALPHABET`
    - _Requirements: 1.5_

- [x] 5. Implement the service layer
  - [x] 5.1 Create `app/services/url_service.py` with the `URLService` class
    - Constructor receives `store: URLStore`, `code_generator: CodeGenerator`, and `base_url: str`
    - Implement `shorten(original_url, custom_code=None, expires_in=None) -> Mapping`
      - Deduplication: if no custom code and URL already exists, return existing mapping
      - Custom code path: check for conflict → raise `ConflictError` if taken
      - Auto-generate path: retry up to 10 times; raise `CodeGenerationError` after exhaustion
      - Compute `expires_at = utcnow() + timedelta(seconds=expires_in)` when provided
      - Persist via `store.create_mapping()`
    - Implement `redirect(short_code) -> Mapping`
      - Raises `NotFoundError` if code missing
      - Raises `ExpiredError` if `mapping.is_expired()` is True; does NOT increment count
      - Increments count (fire-and-forget)
    - Implement `get_stats(short_code) -> Mapping`
      - Raises `NotFoundError` if code missing
      - Returns mapping regardless of expiry state
    - _Requirements: 1.1, 1.2, 1.5, 1.6, 1.7, 2.1, 2.2, 2.3, 2.5, 4.1, 5.1, 5.3, 6.1, 6.2, 6.3, 6.5_

  - [ ]* 5.2 Write property test for shortening idempotence (Property 2)
    - **Property 2: Shortening idempotence**
    - For any valid URL submitted twice without a custom code, assert both calls return the identical `short_code`
    - **Validates: Requirements 1.2**

  - [ ]* 5.3 Write property test for redirect round-trip (Property 3)
    - **Property 3: Redirect round-trip**
    - For any valid URL shortened to a short code, call `redirect()` and assert the returned mapping's `original_url` equals the input URL
    - **Validates: Requirements 2.1**

  - [ ]* 5.4 Write property test for access count monotonically increases (Property 4)
    - **Property 4: Access count monotonically increases**
    - For K redirect calls (K in 1–50) on a non-expired code with initial count N, assert final count equals N + K
    - **Validates: Requirements 2.3, 4.3**

  - [ ]* 5.5 Write property test for expiration boundary (Property 6)
    - **Property 6: Expiration boundary**
    - For any mapping with `expires_at` strictly in the past, assert `redirect()` raises `ExpiredError` and the access count is unchanged
    - **Validates: Requirements 6.2, 6.5**

  - [ ]* 5.6 Write property test for stats completeness (Property 7)
    - **Property 7: Stats completeness**
    - For any existing short code (expired or not), assert `get_stats()` returns HTTP 200 with all required fields: short code, original URL, ISO 8601 creation timestamp, access count, and expiration timestamp when set
    - **Validates: Requirements 4.1, 6.3**

  - [ ]* 5.7 Write property test for custom code conflict detection (Property 8)
    - **Property 8: Custom code conflict detection**
    - For any short code already in the store, assert that `shorten()` with that same custom code raises `ConflictError` regardless of the original URL
    - **Validates: Requirements 5.3**

  - [ ]* 5.8 Write property test for custom code and expiration validation rejection (Property 9)
    - **Property 9: Custom code and expiration validation rejection**
    - For strings with invalid characters or out-of-range lengths, assert the Pydantic schema raises `ValidationError` (422); for `expires_in` values ≤ 0 or > 315,576,000, assert the same
    - **Validates: Requirements 5.2, 5.4, 6.4**

  - [ ]* 5.9 Write property test for expiration timestamp recorded correctly (Property 10)
    - **Property 10: Expiration timestamp recorded correctly**
    - For any valid `expires_in` in 1–315,576,000, assert `expires_at` is within one second of `created_at + timedelta(seconds=expires_in)` and that the same value is readable from the store
    - **Validates: Requirements 6.1**

  - [ ]* 5.10 Write unit tests for service layer
    - `shorten()` creates new mapping for unknown URL
    - `shorten()` returns existing mapping for duplicate URL (no custom code)
    - `shorten()` raises `ConflictError` for taken custom code
    - `shorten()` raises `CodeGenerationError` after 10 failed attempts
    - `redirect()` raises `NotFoundError` for unknown code
    - `redirect()` raises `ExpiredError` for expired mapping; access count unchanged
    - `redirect()` returns 302 even when `increment_access_count` raises (fire-and-forget)
    - `get_stats()` returns mapping for expired code without error
    - _Requirements: 1.2, 1.6, 2.2, 2.5, 4.1, 5.3, 6.2, 6.3, 6.5_

- [~] 6. Checkpoint — Ensure all unit and property tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Implement API routers
  - [~] 7.1 Create `app/api/routers/shorten.py` — `POST /shorten`
    - Accept `ShortenRequest`; call `url_service.shorten()`; return `ShortenResponse` (HTTP 200)
    - Map `ConflictError` → 409, `CodeGenerationError` → 500, `StorageWriteError` → 500
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.7, 5.1, 5.2, 5.3, 5.4, 6.1, 6.4_

  - [~] 7.2 Create `app/api/routers/redirect.py` — `GET /{short_code}`
    - Call `url_service.redirect()`; return `RedirectResponse(url=mapping.original_url, status_code=302)`
    - Map `NotFoundError` → 404, `ExpiredError` → 410, `StorageError` → 503
    - _Requirements: 2.1, 2.2, 2.4, 6.2_

  - [~] 7.3 Create `app/api/routers/stats.py` — `GET /stats/{short_code}`
    - Call `url_service.get_stats()`; return `StatsResponse` (HTTP 200)
    - Map `NotFoundError` → 404, `StorageError` → 503
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 6.3_

  - [~] 7.4 Create `app/api/routers/health.py` — `GET /health`
    - Call `store.health_probe(timeout=1.0)`; return `HealthResponse`
    - Success → 200 `{"status": "operational", "store": "reachable"}`
    - Failure/timeout → 503 `{"status": "degraded", "store": "unreachable"}`
    - _Requirements: 7.1, 7.2, 7.3_

  - [ ]* 7.5 Write unit tests for `POST /shorten` router
    - Happy path returns 200 with `short_url`; duplicate URL returns same code; missing `url` → 422; invalid URL → 422; conflict → 409; storage write failure → 500
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 5.3_

  - [ ]* 7.6 Write unit tests for `GET /{short_code}` router
    - Valid code → 302 with `Location` header; unknown code → 404; expired code → 410; store unreachable → 503; access count failure does not block 302
    - _Requirements: 2.1, 2.2, 2.4, 2.5, 6.2_

  - [ ]* 7.7 Write unit tests for `GET /stats/{short_code}` router
    - Existing code → 200 with all required fields; unknown code → 404; expired code → 200 with `expires_at`; store unreachable → 503
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 6.3_

  - [ ]* 7.8 Write unit tests for `GET /health` router
    - Store reachable → 200 operational; store unreachable/timeout → 503 degraded
    - _Requirements: 7.1, 7.2_

- [ ] 8. Wire everything together in the FastAPI application
  - [~] 8.1 Create `app/dependencies.py` with async dependency providers for `URLStore`, `CodeGenerator`, and `URLService`
    - Use FastAPI `Depends()` and a lifespan context manager for startup/shutdown
    - On startup: call `store.initialize()`; log error and `sys.exit(1)` if `StorageError` raised
    - _Requirements: 3.2, 3.3_

  - [~] 8.2 Create `app/main.py` registering all routers, the global exception handler (returns `{"detail": "..."}` JSON for all `AppError` subclasses), and the lifespan handler
    - Register `routers/shorten.py`, `routers/redirect.py`, `routers/stats.py`, `routers/health.py`
    - _Requirements: 1.1, 2.1, 3.2, 3.3, 4.1, 7.1_

  - [~] 8.3 Create `app/config.py` reading `BASE_URL` and `DATABASE_URL` from environment variables with sensible defaults (`http://localhost:8000` and `sqlite+aiosqlite:///./urls.db`)
    - _Requirements: 1.7_

- [ ] 9. Write integration tests
  - [ ]* 9.1 Write integration test: persistence across store restart
    - Create a mapping, call `store.initialize()` fresh on the same DB file, assert the mapping is still resolvable
    - _Requirements: 3.1, 3.2_

  - [ ]* 9.2 Write integration test: redirect increments count visible in stats
    - Shorten a URL, redirect twice, call `/stats/{short_code}`, assert `access_count == 2`
    - _Requirements: 2.3, 4.3_

  - [ ]* 9.3 Write integration test: expired link returns 410
    - Create a mapping with `expires_in=1`, sleep 2 seconds, assert GET `/{short_code}` returns 410 and count is not incremented
    - _Requirements: 6.2, 6.5_

- [~] 10. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Checkpoints (tasks 6 and 10) provide incremental validation gates
- Property tests use Hypothesis with `@settings(max_examples=100)` minimum; tag each test with `# Feature: python-url-shortener, Property N: <property_text>`
- Unit tests mock `URLStore` with `unittest.mock.AsyncMock`; property tests for the store layer use an in-memory SQLite instance
- `increment_access_count` is fire-and-forget: failures are logged at WARNING level but must not propagate to the client
- The `BASE_URL` config value is used to construct all `short_url` values returned in responses

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["2.1", "3.1", "4.1"] },
    { "id": 1, "tasks": ["2.2", "3.2", "3.3", "4.2", "4.3", "5.1"] },
    { "id": 2, "tasks": ["5.2", "5.3", "5.4", "5.5", "5.6", "5.7", "5.8", "5.9", "5.10", "7.1", "7.2", "7.3", "7.4"] },
    { "id": 3, "tasks": ["7.5", "7.6", "7.7", "7.8", "8.1"] },
    { "id": 4, "tasks": ["8.2", "8.3"] },
    { "id": 5, "tasks": ["9.1", "9.2", "9.3"] }
  ]
}
```
