# 🥗 NutriCoach — Nutritional Assistant with Persistent Memory

Final project for the **AI Agents with Persistent Memory** course at BSG Institute.

NutriCoach is a digital nutritional coach that combines:
- 👤 **Medical-nutritional profiles** persisted in Firestore.
- 🧠 **Long-term semantic memory** (not just message logs).
- 🔍 **Real-time nutritional data** via USDA FoodData Central.
- 📰 **News and recalls** via Tavily.
- 💸 **Model router** that reduces costs by ~70% (gpt-5-mini ↔ gpt-5).
- 🔐 **Guardrails** against prompt injection and medical disclaimers.

## 📁 Structure

```
nutricoach/
├── backend/
│   ├── agent/
│   │   ├── agent.py              # LangChain composition + system prompt
│   │   ├── model_router.py       # Mini ↔ full heuristic (gpt-5-mini / gpt-5)
│   │   └── tools_langchain.py    # @tool USDA + @tool Tavily
│   ├── data/
│   │   └── seed_clients.json     # 3 rich profiles
│   ├── firebase/
│   │   ├── client.py             # Firestore AsyncClient
│   │   ├── clients.py            # Client CRUD
│   │   ├── chat_history.py       # Conversation CRUD
│   │   └── long_term_memory.py   # Fact extraction + compaction
│   ├── routers/
│   │   ├── agent_router.py       # /agent/stream with robust SSE
│   │   └── clients_router.py     # /clients
│   ├── security/
│   │   └── guardrails.py         # Sanitization + anti-injection
│   ├── tools/
│   │   └── nutrition_tools.py    # USDA + Tavily clients
│   ├── config.py
│   ├── Dockerfile
│   ├── firestore.rules
│   ├── main.py
│   ├── requirements.txt
│   └── seed.py
├── frontend/
│   └── ... (React + Vite)
├── CASO_DE_USO.md
└── README.md
```

## 🚀 Local Setup

### 1. External Services

Before starting the backend:

| Service | Purpose | Plan |
|---|---|---|
| Firebase Firestore | Client data and conversations | Spark (free) |
| OpenAI API | LLM | $5 USD is sufficient |
| USDA FoodData Central | Nutritional data | Free (1000 req/h) — [signup](https://fdc.nal.usda.gov/api-key-signup/) |
| Tavily | Web search | 1000 searches/month (free) |

### 2. Configure environment

The project uses a single `.env` at the **repository root**:

```bash
cp .env.example .env
```

Edit `.env` and fill in your credentials:

```env
OPENAI_API_KEY=sk-proj-...
TAVILY_API_KEY=tvly-...
USDA_API_KEY=DEMO_KEY          # or your real key
GOOGLE_APPLICATION_CREDENTIALS=./firebase-service-account.json
FIREBASE_PROJECT_ID=your-firebase-project-id
CORS_ORIGINS=http://localhost:5173
VITE_API_BASE=                 # leave empty for local dev
LOG_LEVEL=INFO
```

Also place your Firebase service account file at `backend/firebase-service-account.json`.

### 3. Backend (Terminal 1)

**Option A — uv (recommended, faster)**

[uv](https://docs.astral.sh/uv/) is a fast Python package manager. Install it once:

```bash
# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Mac / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then:

```bash
cd backend

# Create virtual environment and install dependencies in one step
uv venv
uv pip install -r requirements.txt

# Activate the environment
source .venv/Scripts/activate   # Windows (Git Bash / WSL)
# source .venv/bin/activate     # Mac / Linux

# Load the 3 seed clients into Firestore (run once)
python seed.py

# Start the server
uvicorn main:app --reload --port 8000
```

**Option B — pip (standard)**

```bash
cd backend

python -m venv venv
source venv/Scripts/activate    # Windows (Git Bash / WSL)
# source venv/bin/activate      # Mac / Linux

pip install -r requirements.txt
python seed.py
uvicorn main:app --reload --port 8000
```

Verify it works:
```bash
curl http://localhost:8000/health
# {"status":"ok"}

curl http://localhost:8000/clients
# Lists Ana, Marco and Lucía
```

Also available: `http://localhost:8000/docs` → Swagger UI

### 4. Frontend (Terminal 2)

```bash
cd frontend
npm install
npm run dev
# App running at http://localhost:5173
```

Open `http://localhost:5173` in your browser. You should see the sidebar with the 3 clients.

## 🚂 Deploy to Railway (Recommended)

Railway deploys both services directly from your GitHub repo — no CLI needed.

### 1. Backend service

1. [railway.app](https://railway.app) → **New Project → GitHub Repo** → select this repo
2. **Settings → Root Directory**: `backend`
3. Add these environment variables in Railway dashboard:

| Variable | Value |
|---|---|
| `OPENAI_API_KEY` | your key |
| `TAVILY_API_KEY` | your key |
| `USDA_API_KEY` | `DEMO_KEY` or your key |
| `FIREBASE_PROJECT_ID` | your Firebase project ID |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | full contents of `firebase-service-account.json` |
| `CORS_ORIGINS` | `https://your-frontend.up.railway.app,http://localhost:5173` |
| `LOG_LEVEL` | `INFO` |

4. **Settings → Networking → Generate Domain** → copy the URL

### 2. Frontend service

1. Same project → **New Service → GitHub Repo** → same repo
2. **Settings → Root Directory**: `frontend`
3. Add one variable:

| Variable | Value |
|---|---|
| `VITE_API_BASE` | `https://your-backend.up.railway.app` (full URL with https://) |

4. **Settings → Networking → Generate Domain**
5. Update `CORS_ORIGINS` in the backend service with the frontend URL and redeploy

### 3. Firestore index (required)

On first use, Firestore will return an error with a direct link to create the required index:
- Collection: `conversations`
- Fields: `client_id` Ascending, `updated_at` Descending

Click the link in the error to create it instantly.

---

## ☁️ Deploy to Cloud Run (Public URL)

### Prerequisites
- `gcloud` CLI authenticated against your project.
- Cloud Run and Cloud Build APIs enabled.

### 1. Upload Credentials as Secrets

```bash
# Firebase service account
gcloud secrets create firebase-sa --data-file=backend/firebase-service-account.json

# API keys
echo -n "$OPENAI_API_KEY"  | gcloud secrets create openai-key  --data-file=-
echo -n "$TAVILY_API_KEY"  | gcloud secrets create tavily-key  --data-file=-
echo -n "$USDA_API_KEY"    | gcloud secrets create usda-key    --data-file=-
```

### 2. Build & Deploy Backend

```bash
PROJECT_ID=$(gcloud config get-value project)
REGION=us-central1

gcloud builds submit backend/ --tag gcr.io/$PROJECT_ID/nutricoach-backend

gcloud run deploy nutricoach-backend \
  --image gcr.io/$PROJECT_ID/nutricoach-backend \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 5 \
  --timeout 300 \
  --concurrency 20 \
  --set-env-vars "FIREBASE_PROJECT_ID=$PROJECT_ID" \
  --set-env-vars "GOOGLE_APPLICATION_CREDENTIALS=/secrets/firebase-sa.json" \
  --set-env-vars "CORS_ORIGINS=https://your-frontend.web.app,http://localhost:5173" \
  --set-secrets "/secrets/firebase-sa.json=firebase-sa:latest" \
  --update-secrets "OPENAI_API_KEY=openai-key:latest" \
  --update-secrets "TAVILY_API_KEY=tavily-key:latest" \
  --update-secrets "USDA_API_KEY=usda-key:latest"
```

> **Note on SSE**: Cloud Run natively supports SSE as long as the request
> does not exceed the configured `--timeout` (here 300s = 5 min). The header
> `X-Accel-Buffering: no` returned by our endpoint prevents intermediate buffering.

### 3. Deploy Frontend to Firebase Hosting (or Cloud Run)

```bash
cd frontend
echo "VITE_API_BASE=https://nutricoach-backend-xxxx-uc.a.run.app" > .env.production
npm run build

# Option A: Firebase Hosting
firebase init hosting
firebase deploy --only hosting

# Option B: Cloud Run with Nginx
# (see frontend/Dockerfile if added)
```

## 🧪 Post-Deploy Smoke Test

```bash
BASE=https://your-backend.run.app

curl $BASE/health
# {"status":"ok"}

curl $BASE/clients
# List of 3 clients

# Stream test (Ctrl+C to stop)
curl -N "$BASE/agent/stream?client_id=client_001&message=Hello%2C+what+can+I+have+for+breakfast+today%3F"
```

## 🐛 Troubleshooting

| Symptom | Probable Cause | Fix |
|---|---|---|
| `Firestore: index not found` | Missing `client_id ASC, updated_at DESC` index in `conversations` | Create it using the link provided in the error message |
| Tokens arrive all at once | Proxy buffering | Verify `X-Accel-Buffering: no` header (already included) |
| `429 rate limit exceeded` | Rate limiter triggered | Wait 60s. For intensive tests, increase `_RATE_MAX_REQS` |
| `400 rejected: empty_message` | Frontend sent an empty string | Validate input before calling fetch |
| Agent never uses USDA | Unclear docstring | Check `tools_langchain.py`, add more domain-specific examples |
| Costs are too high | Routing always forces `gpt-5` | Log `routing.reason` in Cloud Logging and adjust heuristics |

## 📊 Metrics to Monitor

Useful Cloud Logging queries:

```
# Model tier distribution
jsonPayload.message =~ "routing client_id" | summarize count by jsonPayload.model

# P95 Latency
resource.type = "cloud_run_revision" | latency.p95

# Fact extraction errors
jsonPayload.message =~ "fact_extraction_(parse|llm)_error"
```


