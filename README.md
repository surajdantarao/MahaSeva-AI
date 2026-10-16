# MahaSeva AI — Centralized Maharashtra Government Scheme Platform

MahaSeva AI is an automated, centralized Maharashtra Government Scheme Discovery, Deadline Monitoring, and Citizen Assistance Platform. It automatically discovers newly announced schemes, monitors official departmental portals for updates, extracts and verifies application dates, distinguishes active schemes from expired and upcoming schemes, and provides high-quality AI assistance in Marathi, English, and Romanized Marathi.

---

## 🏛️ Key System Capabilities

1. **Automatic Government Source Monitoring & Autonomous Scheduler**:
   - Continuous background monitoring runner (`backend/scheduler.py`) that starts with the FastAPI application lifespan.
   - Monitors official departmental scheme directories, MahaDBT, Aaple Sarkar, and Government Resolutions (GRs).
   - Content hashing (SHA-256), change detection, and incremental updates without requiring manual crawler triggers.
   - Concurrency locking preventing overlapping runs; bounded exponential backoff retries.

2. **Dedicated Application Deadline & Status Engine**:
   - Centralized, authoritative calculation service (`backend/status_engine.py`) operating strictly in `Asia/Kolkata` timezone.
   - Evaluates machine-readable states: `open`, `closing_soon`, `upcoming`, `closed`, `no_deadline_published`, `date_unverified`, `temporarily_unavailable`, `discontinued`.
   - Interprets closing times conservatively: if no time is specified, window remains valid until 23:59:59 on deadline day.
   - Standard bilingual notice for schemes without published deadlines:
     - English: *"No application deadline published by the available official sources."*
     - Marathi: *"उपलब्ध अधिकृत स्रोतांमध्ये अर्जाची अंतिम तारीख नमूद केलेली नाही."*
   - Daily automatic recalculation and support for fixed test clock mock fixtures.

3. **Dynamic Homepage Scheme Listings**:
   - Scheme information generated dynamically from the database (`GET /api/v1/schemes/homepage-sections`):
     - **Applications Open Now**
     - **Closing Soon**
     - **Upcoming Schemes**
     - **No Deadline Published**
     - **Recently Announced Schemes**
     - **Recently Updated Schemes**
     - **Closed Application Windows**
   - Direct links to official source portals and verified application links.

4. **On-Card Contextual AI Scheme Chat**:
   - One-click temporary chat (`Ask AI About This Scheme`) passing unique scheme ID to `POST /api/v1/ai/scheme-chat`.
   - Grounded specifically on latest verified scheme records, status engine calculations, and official application portals.
   - Completely ephemeral session: cleared on navigation, refresh, or switching schemes; zero database persistence.

5. **High-Quality Bilingual AI Assistant & Answer Validation**:
   - First-class bilingual RAG supporting **English**, **मराठी (Marathi)**, and **Romanized Marathi** (e.g. *"Ya scheme chi last date kay aahe?"*).
   - Automated Answer Quality Checks:
     - Rejects unverified URLs not present in approved source registries.
     - Detects and flags date or active/expired contradictions against the status engine.
   - Privacy Shield: Automatically detects and blocks accidental submission of Aadhaar or bank account numbers.

6. **Administrative Verification & Change Approval Workflow**:
   - Role-based JWT authentication (`/api/v1/admin/*`).
   - Detected Changes Queue (`GET /api/v1/admin/changes`): review and approve deadline extensions, new rounds, and eligibility updates before public publication.
   - Source Registry Management (`/api/v1/admin/sources`): configure monitoring frequency, priority, and manual scan triggers.
   - Immutable audit trail (`verification_audits` table).

---

## 🛠️ Technology Stack

- **Frontend**: React 19, TypeScript, Vite 8, Modern Accessible CSS (Outfit & Noto Sans Devanagari typography).
- **Backend**: Python 3.12, FastAPI, SQLAlchemy ORM, Pydantic V2, PyMySQL, PyJWT, bcrypt.
- **Database**: MySQL (`mahaseva_ai` database).
- **Collection & Extraction Layer**: `collector.py`, `backend/date_extractor.py`, BeautifulSoup4, Trafilatura, PyMuPDF.

---

## 🚀 Setup & Execution Guide (Windows)

### 1. Prerequisites
- Python 3.12 (with active `.venv`)
- Node.js (v18+) & npm
- Local MySQL server running with database `mahaseva_ai`

### 2. Environment Configuration
Ensure your `.env` contains valid credentials:
```env
DATABASE_URL=mysql+pymysql://mahaseva_app:Suraj%40123@127.0.0.1:3306/mahaseva_ai?charset=utf8mb4
SECRET_KEY=your_secure_random_key_here
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
AI_PROVIDER=rule_based
```

### 3. Install Dependencies
```powershell
# Python backend dependencies
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt pytest httpx pyjwt bcrypt

# Frontend dependencies
cd frontend\frontend
npm install
cd ..\..
```

### 4. Database Migration & Candidate Import
Run the non-destructive migration script to ensure all new tables and columns exist:
```powershell
$env:PYTHONPATH="."
.\.venv\Scripts\python -m backend.migrate_db
```
Sync candidate records from `output/schemes_candidates.csv` with automated date extraction:
```powershell
.\.venv\Scripts\python -m backend.import_csv
```

### 5. Officer Account Setup
To create an administrator account:
```powershell
$env:PYTHONPATH="."
.\.venv\Scripts\python -m backend.manage_admin create --username admin --email admin@mahaseva.gov.in --password "MahaSevaAdmin@2026!" --role admin
```

### 6. Run Complete Automated Test Suite (41 Tests)
Execute both backend and master 26-criteria test suites:
```powershell
cmd.exe /c "set PYTHONPATH=. && .venv\Scripts\python.exe -m pytest -v tests/test_backend.py tests/test_master.py"
```

### 7. Run the Application

**Start the FastAPI Backend (Port 8000):**
```powershell
cmd.exe /c "set PYTHONPATH=. && .venv\Scripts\uvicorn.exe backend.main:app --host 127.0.0.1 --port 8000 --reload"
```

**Start the React Frontend (Port 5173):**
```powershell
npm --prefix frontend/frontend run dev
```
Open `http://localhost:5173` in your browser.

**Build Production Frontend:**
```powershell
npm --prefix frontend/frontend run build
```

---

## 📡 Key API Endpoints

### Citizen Discovery & AI
- `GET /api/v1/schemes/homepage-sections` — Dynamic homepage groups (Open now, Closing soon, Upcoming, No deadline, Recently announced/updated, Closed).
- `GET /api/v1/schemes` — Multi-parameter search (`q`, `department`, `category`, `deadline_status`, `verification_status`, `sort_by`, `limit`, `offset`).
- `GET /api/v1/schemes/{id}` — Full scheme details, verified application deadline, and historical application rounds.
- `POST /api/v1/ai/ask` — Citizen AI Assistant (Grounded bilingual RAG in English, Marathi, and Romanized Marathi).
- `POST /api/v1/ai/scheme-chat` — Temporary contextual scheme chat on card (ephemeral, zero persistence).
- `GET /api/v1/sources` — Official registered government portals and health status.

### Officer & Admin Workflow (Requires Bearer JWT)
- `POST /api/v1/admin/auth/login` — Authenticate officer credentials and issue JWT.
- `GET /api/v1/admin/changes` — Review queue of detected scheme changes and deadline extensions.
- `POST /api/v1/admin/changes/{id}/review` — Approve or reject detected changes.
- `POST /api/v1/admin/schemes/{id}/review` — Update scheme verification status, edit fields, and record audit log.
- `GET /api/v1/admin/monitoring/stats` — Live background scheduler health and metrics.
- `POST /api/v1/admin/monitoring/trigger` — Trigger immediate manual monitoring pass.
