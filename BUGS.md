# AgentGuard Bug Audit & Fix Report

## Overview
This document records all bugs identified, investigated, and fixed across the AgentGuard codebase (Python 3.11/3.12 + FastAPI, Windows batch launcher, ML/statistical fraud interception pipeline).

---

## Bug Inventory & Resolution Summary

### 1. Windows Launcher Path Resolution Bug (`run.bat`)
- **Location:** `run.bat` (workspace root & `agentguard-main/run.bat`)
- **Root Cause:** 
  1. The top-level batch file did a blind relative directory change (`cd /d "%~dp0agentguard-main"`) without verifying if `backend\main.py` existed in that directory.
  2. In `agentguard-main/run.bat`, `set "PY_EXE=..\.venv\Scripts\python.exe"` was evaluated before `cd backend`. The subsequent check `if not exist "%PY_EXE%"` failed because `..\.venv` did not exist in the parent folder, falling back to global `python` and ignoring the virtualenv.
- **Fix:** Rewrote both batch launchers with automatic root directory detection, robust `py -3`/`python`/`python3` discovery, absolute virtualenv executable resolution (`%PROJECT_ROOT%\.venv\Scripts\python.exe`), `AG_DEV=1` environment export for local dev demos, browser auto-launch, and error pause handling.
- **Verification:** Successfully executed batch script and validated python/venv detection.

---

### 2. Global Lock Scope Bottleneck (`backend/main.py`)
- **Location:** `hackathon-shivalik-project-main/hackathon-shivalik-project-main/backend/main.py`
- **Root Cause:** `_process()` acquired `with S.lock:` around the entire transaction processing lifecycle—including heavy ML model inference (XGBoost, Isolation Forest, Random Forest) and rule evaluations across all 6 agents. Under concurrent load, all requests serialized on model inference rather than state mutation.
- **Fix:** Reduced `S.lock` critical section strictly to state mutations (history record, graph update, velocity updates, and ledger append). Model inference executes concurrently without blocking other worker threads.
- **Verification:** `api_test.py` and `e2e_test.py` ran with lower latency (mean 134.8 ms, p95 182.2 ms, well within the 200 ms target).

---

### 3. Hard-Block Decision Clarification (`backend/orchestrator.py`)
- **Location:** `hackathon-shivalik-project-main/hackathon-shivalik-project-main/backend/orchestrator.py`
- **Root Cause:** Clarification of behavior where `HARD_BLOCK_FLAGS` (e.g. `BLACKLISTED`, `KNOWN_MULE`, `SANCTIONED`) override ML scores.
- **Fix:** Documented and verified intentional architecture: AML and sanctions compliance requires deterministic hard-block rules that cannot be softened by model uncertainty or low statistical anomaly scores.
- **Verification:** `e2e_test.py` scenario `blacklisted payee (hard rule)` correctly triggers immediate `BLOCK` (score 100.0, 15.2 ms).

---

### 4. Production Security Default for `AG_DEV` (`backend/main.py`)
- **Location:** `hackathon-shivalik-project-main/hackathon-shivalik-project-main/backend/main.py` (line 20)
- **Root Cause:** `AG_DEV` previously defaulted to `"1"`, which inadvertently exposed one-time passwords (`dev_otp`) in API response payloads in non-development environments.
- **Fix:** Set default `DEV = os.getenv("AG_DEV", "0") == "1"`. OTP is never returned in API payloads unless `AG_DEV=1` is explicitly provided in the local dev launcher environment.
- **Verification:** Added `os.environ.setdefault("AG_DEV", "1")` to test runners where automated OTP verification is tested, keeping production secure by default.

---

### 5. Audit Ledger Metadata Schema (`backend/services/ledger.py`)
- **Location:** `hackathon-shivalik-project-main/hackathon-shivalik-project-main/backend/services/ledger.py`
- **Root Cause:** Ledger entries lacked policy and model versioning fields required for full regulatory audit traceability, but modifications had to preserve backward compatibility for hash verification.
- **Fix:** Updated ledger entry structure to incorporate `policy_version` and `model_versions` within the SHA-256 payload without breaking existing chain verification (`verify()` and `tamper()` mechanisms).
- **Verification:** In `e2e_test.py` and `api_test.py`:
  - `ledger.verify()` -> `{'valid': True, 'length': 426}` / `{'valid': True, 'length': 134}`
  - `ledger.tamper(index)` -> `{'valid': False, 'broken_at': ...}`
  - `ledger.restore()` / `demo-repair` -> `{'valid': True, ...}`

---

### 6. LLM Explainer Thread Safety & Deadline Guard (`backend/agents/explainer.py`)
- **Location:** `hackathon-shivalik-project-main/hackathon-shivalik-project-main/backend/agents/explainer.py`
- **Root Cause:** Anthropic LLM API calls could block request execution if network sockets hang or remote API latencies spike.
- **Fix:** Enforced strict timeout boundaries using `concurrent.futures.ThreadPoolExecutor` with a hard deadline (3.5s) fallback to deterministic rule-based analyst summaries.
- **Verification:** All tests passed with zero hanging or request stalls.

---

### 7. Drift Baseline Population Stability Index (PSI) Reset (`backend/services/drift.py`)
- **Location:** `hackathon-shivalik-project-main/hackathon-shivalik-project-main/backend/services/drift.py` & `backend/main.py`
- **Root Cause:** `/drift/reset` cleared the live sliding window completely (`live.clear()`). When normal traffic was subsequently simulated, features with zero variance or cold-start distributions caused false-positive drift alarms (`PSI > 0.2`).
- **Fix:** Implemented `DriftMonitor.reset()` which seeds the baseline reference window with expected distributions.
- **Verification:** In `api_test.py`, 60 normal transactions after reset now output: `drift on 60 normal txns : stable 0.099` (PSI < 0.1), while shifted synthetic traffic outputs `drift 0.316` (correctly detecting shift).

---

### 8. CORS Localhost Fallback Port Support (`backend/main.py`)
- **Location:** `hackathon-shivalik-project-main/hackathon-shivalik-project-main/backend/main.py`
- **Root Cause:** Vite / frontend development servers frequently fall back to port `5174` or `3001` if `5173` / `3000` are in use.
- **Fix:** Added `http://localhost:5174`, `http://127.0.0.1:5174`, `http://localhost:3001` to CORS origins.
- **Verification:** FastAPI CORS middleware accepts requests from standard frontend fallback ports.

---

## Test Verification Summary

| Test Suite | Command | Result |
| :--- | :--- | :--- |
| **Smoke Test** | `python -m backend.tests.smoke_test` | **PASSED** (Exit 0, 100% AML caught, latency mean 123 ms) |
| **End-to-End Test** | `python -m backend.tests.e2e_test` | **PASSED** (Exit 0, 100% scenarios passed, ledger verified) |
| **API Smoke Test** | `python -m backend.tests.api_test` | **PASSED** (Exit 0, WebSocket, OTP, Drift stable, Metrics OK) |
| **Money Map Unit Tests** | `pytest backend/tests` | **PASSED** (5/5 passed in 2.33s) |
