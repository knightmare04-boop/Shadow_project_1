# Execution & Deployment Guide: The Self-Auditing Ledger

This document details how to set up, run, test, and demonstrate **The Self-Auditing Ledger** across both **Instant Demo Mode** (zero-infrastructure local evaluation) and the **Full Production Stack** (Docker, PostgreSQL 16, Redis 7, FastAPI, and Vite React).

---

## 1. System Architecture & Port Map

The application consists of three integrated tiers:

| Service | Technology | Port | Description |
| :--- | :--- | :--- | :--- |
| **Web Console** | React 18, Vite, TypeScript | `5173` | Forensic audit console, alert queue, and federated consortium dashboard |
| **Backend API** | FastAPI, SQLAlchemy 2 (Async) | `8000` | REST API, RFC 9457 error handling, scoring pipeline, federated endpoints |
| **Database** | PostgreSQL 16 Alpine | `5432` | System of record for double-entry GL ledger, journal vouchers, invoices |
| **Cache & Locks** | Redis 7 Alpine | `6379` | Distributed locks, idempotency key cache, response caching |
| **Graph DB** *(Optional)* | Neo4j 5 Community | `7474` / `7687` | Auxiliary graph visualization sink (system runs seamlessly without it) |

---

## 2. Fast Track A: 10-Second Instant Demo (No Docker Required)

If you are presenting on a laptop without Docker Desktop running, or need to quickly demonstrate the system to evaluators:

### Step 1: Start the Web Client
From the repository root in PowerShell or Command Prompt:
```powershell
cd web
cmd.exe /c "npm run dev"
```
*(Note: Using `cmd.exe /c` avoids Windows PowerShell script execution policy restrictions).*

### Step 2: Open and Log In
1. Open your browser to: **`http://localhost:5173/login`**
2. Click any of the **1-Click Quick Dev Sign-in** buttons:
   - 🛡️ **Forensic Auditor:** `auditor@shadow-ledger.app` *(Recommended for fraud review)*
   - ⚡ **Administrator:** `admin@shadow-ledger.app`
   - 📝 **ERP Clerk:** `clerk@shadow-ledger.app`
   - *(Default dev password: `devpassword123`)*

> [!TIP]
> **Graceful Offline Fallback Active:**
> If the backend API on port `8000` is offline, the web client automatically activates **Demo Mode**. You can immediately inspect:
> - The **Alert Queue** with interactive TreeSHAP waterfall charts.
> - The novel **Federated Network** consortium dashboard with BankSim benchmark metrics.
> - The interactive **Decentralized Multi-Bank Consensus Simulator**.

---

## 3. Fast Track B: Full Production Environment (With Docker & Database)

Follow these steps for full end-to-end execution with the real PostgreSQL database and FastAPI backend.

### Step 1: Environment File Setup
Copy the sample environment file to `.env`:
```powershell
copy .env.example .env
```
Default connection strings are already pre-configured for local development:
```env
ENV=development
DATABASE_URL=postgresql+asyncpg://ledger:ledger_dev_password@localhost:5432/shadow_ledger
DATABASE_URL_SYNC=postgresql+psycopg://ledger:ledger_dev_password@localhost:5432/shadow_ledger
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=dev_secret_key_change_in_production_32bytes_min
```

### Step 2: Start Infrastructure Containers
Ensure Docker Desktop is running, then spin up the database and Redis services:
```powershell
docker compose -f infra/docker-compose.yml up -d postgres redis
```
Verify that the containers are healthy:
```powershell
docker ps
```
You should see `ledger-postgres` and `ledger-redis` with status `healthy` or `Up`.

### Step 3: Python Virtual Environment & Dependencies
Set up a Python 3.11 virtual environment and install dependencies:
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[test,explain]"
```
*(Or install core requirements: `pip install fastapi uvicorn sqlalchemy asyncpg psycopg pydantic-settings redis xgboost scikit-learn shap pyarrow`)*

### Step 4: Run Database Migrations & Seed Initial Data
Initialize the database schema and seed the chart of accounts, initial users, and open fiscal period:
```powershell
# Run database schema migrations
alembic upgrade head

# Seed core chart of accounts and default RBAC accounts
python tools/seed_core.py
```
Expected output:
```
Seeded 13 GL accounts
Seeded 3 users: clerk@shadow-ledger.app, auditor@shadow-ledger.app, admin@shadow-ledger.app
Seeded open fiscal period 2026-09
Core seed complete.
```

### Step 5: Launch the FastAPI Backend
Start the backend server on port `8000`:
```powershell
uvicorn app.main:app --reload --port 8000
```
- API is live at: `http://localhost:8000`
- Interactive Swagger API docs: **`http://localhost:8000/docs`**
- Health check: `http://localhost:8000/health`

### Step 6: Launch the Web Frontend
In a separate terminal:
```powershell
cd web
cmd.exe /c "npm run dev"
```
Open **`http://localhost:5173`** to access the complete application.

---

## 4. Running the Novel Federated Learning Experiments

To reproduce the scientific benchmark results comparing **Isolated Local** vs. **Uniform FedAvg** vs. **FedProx Score Ensemble** vs. **Centralized Upper Bound**:

### 1. BankSim 3-Seed Consortium Benchmark
Runs a 4-institution non-IID Dirichlet partition across 3 independent random seeds:
```powershell
python -m experiments.federated --dataset banksim --k 4 --seeds 42 43 44
```
**Expected Verified Output:**
```
================================================================================
FEDERATED CONSORTIUM BENCHMARK REPORT (Dataset: BankSim, K=4)
================================================================================
Isolated Local (Mean ± Std)     : 0.8659 ± 0.0381 PR-AUC
Uniform FedAvg (Mean ± Std)     : 0.9024 ± 0.0210 PR-AUC
FedProx Score Ensemble (μ=0.01) : 0.9239 ± 0.0142 PR-AUC
Centralized Upper Bound         : 0.9343 ± 0.0118 PR-AUC
--------------------------------------------------------------------------------
Consortium Collaboration Lift   : +0.0580 PR-AUC (+6.7% gain)
Centralized Model Parity        : 98.89% parity (Zero raw data shared)
================================================================================
```

### 2. Synthetic ERP Cross-Subsidiary Benchmark
Evaluates multi-subsidiary round-tripping and invoice lapping:
```powershell
python -m experiments.federated --dataset synth_erp --k 4 --seeds 42
```

### 3. Running the Automated Test Suite
Verify that all federated partitioners, clients, and servers pass test assertions:
```powershell
python -m unittest tests/test_federated.py
```
Output:
```
Ran 4 tests in 0.867s - OK
```

---

## 5. Default Login Accounts & RBAC Roles

All default seed accounts share the development password: **`devpassword123`**

| Role | Email | Password | Access Capabilities |
| :--- | :--- | :--- | :--- |
| 🛡️ **Forensic Auditor** | `auditor@shadow-ledger.app` | `devpassword123` | Alert queue, SHAP waterfall investigations, Federated consortium dashboard |
| ⚡ **System Administrator** | `admin@shadow-ledger.app` | `devpassword123` | Full administrative access, system metrics, GL chart of accounts, user management |
| 📝 **ERP Clerk** | `clerk@shadow-ledger.app` | `devpassword123` | Vendors, Invoices, Purchase Orders, Payment submission |

---

## 6. Review & Presentation Artifacts

In addition to the running app, two presentation-ready documentation files are available:

1. **`PROJECT_SHOWCASE.html`**:
   - A standalone, modern HTML presentation file with clean UI/UX.
   - Contains the full executive summary, novelty crisis explanation, mathematical formulations, benchmark tables, side-by-side comparison matrix, viva defense cheatsheet, and a **built-in interactive consensus simulator**.
   - **How to view:** Double-click or open `PROJECT_SHOWCASE.html` in any web browser.

2. **`docs/FINAL_REPORT.md`**:
   - The formal academic report detailing the system specification and empirical results.

---

## 7. Common Troubleshooting & Windows Tips

### A. PowerShell Script Execution Disabled (`UnauthorizedAccess`)
- **Error:** `File C:\Program Files\nodejs\npm.ps1 cannot be loaded because running scripts is disabled on this system.`
- **Fix:** Prefix commands with `cmd.exe /c`, for example:
  ```powershell
  cmd.exe /c "npm run dev"
  cmd.exe /c "npm run build"
  ```
  Or temporarily allow scripts in your current PowerShell session:
  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  ```

### B. Docker Daemon Not Responding
- **Error:** `failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine`
- **Fix:** Open **Docker Desktop** from your Windows Start Menu and wait for the engine indicator to turn green before running `docker compose up`. If Docker cannot be started, you can still evaluate the complete frontend using Fast Track A (Demo Mode).

### C. Port 5432 or 8000 Already in Use
- Check for existing processes using PowerShell:
  ```powershell
  Get-Process -Id (Get-NetTCPConnection -LocalPort 5432).OwningProcess
  ```
- Either terminate the conflicting service or adjust the port alias in `.env` (e.g., `POSTGRES_PORT=5433`).
