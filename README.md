# 🥗 NutriCoach — Asistente Nutricional con Memoria Persistente

Proyecto final del curso **Agentes de IA con Memoria Persistente** del BSG Institute.

NutriCoach es un coach nutricional digital que combina:
- 👤 **Perfiles médico-nutricionales** persistidos en Firestore.
- 🧠 **Memoria semántica de largo plazo** (no solo logs de mensajes).
- 🔍 **Datos nutricionales en tiempo real** vía USDA FoodData Central.
- 📰 **Noticias y recalls** vía Tavily.
- 💸 **Modelo router** que reduce costo ~70% (gpt-5-mini ↔ gpt-5).
- 🔐 **Guardrails** contra prompt injection y disclaimers médicos.

## 📁 Estructura

```
nutricoach/
├── backend/
│   ├── agent/
│   │   ├── agent.py              # Composición LangChain + system prompt
│   │   ├── model_router.py       # Heurística mini ↔ full (gpt-5-mini / gpt-5)
│   │   └── tools_langchain.py    # @tool USDA + @tool Tavily
│   ├── data/
│   │   └── seed_clients.json     # 3 perfiles ricos
│   ├── firebase/
│   │   ├── client.py             # AsyncClient Firestore
│   │   ├── clients.py            # CRUD clientes
│   │   ├── chat_history.py       # CRUD conversaciones
│   │   └── long_term_memory.py   # Extracción de facts + compactación
│   ├── routers/
│   │   ├── agent_router.py       # /agent/stream con SSE robusto
│   │   └── clients_router.py     # /clients
│   ├── security/
│   │   └── guardrails.py         # Sanitización + anti-injection
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

## 🚀 Setup local

### 1. Servicios externos

Antes de arrancar el backend:

| Servicio | Para qué | Plan |
|---|---|---|
| Firebase Firestore | Datos del cliente y conversaciones | Spark (gratis) |
| OpenAI API | LLM | $5 USD bastan |
| USDA FoodData Central | Datos nutricionales | Gratis (1000 req/h) — [signup](https://fdc.nal.usda.gov/api-key-signup/) |
| Tavily | Búsqueda web | 1000 búsquedas/mes (gratis) |

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate         # Linux/Mac
# venv\Scripts\activate          # Windows
pip install -r requirements.txt

cp .env.example .env             # luego editar con tus llaves
# colocar firebase-service-account.json en backend/

python seed.py                   # carga los 3 perfiles
uvicorn main:app --reload --port 8000
```

Verificación:
- `http://localhost:8000/health` → `{"status": "ok"}`
- `http://localhost:8000/docs` → Swagger
- `http://localhost:8000/clients` → 3 perfiles cargados

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
# http://localhost:5173
```

## ☁️ Deploy a Cloud Run (URL pública)

### Pre-requisitos
- `gcloud` CLI autenticado contra tu proyecto.
- API de Cloud Run y Cloud Build habilitadas.

### 1. Subir credenciales como Secret

```bash
# Service account de Firebase
gcloud secrets create firebase-sa --data-file=backend/firebase-service-account.json

# API keys
echo -n "$OPENAI_API_KEY"  | gcloud secrets create openai-key  --data-file=-
echo -n "$TAVILY_API_KEY"  | gcloud secrets create tavily-key  --data-file=-
echo -n "$USDA_API_KEY"    | gcloud secrets create usda-key    --data-file=-
```

### 2. Build & Deploy del backend

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
  --set-env-vars "CORS_ORIGINS=https://tu-frontend.web.app,http://localhost:5173" \
  --set-secrets "/secrets/firebase-sa.json=firebase-sa:latest" \
  --update-secrets "OPENAI_API_KEY=openai-key:latest" \
  --update-secrets "TAVILY_API_KEY=tavily-key:latest" \
  --update-secrets "USDA_API_KEY=usda-key:latest"
```

> **Nota sobre SSE**: Cloud Run soporta SSE de forma nativa siempre que el
> request no exceda el `--timeout` configurado (aquí 300s = 5 min). El header
> `X-Accel-Buffering: no` que ya devuelve nuestro endpoint previene buffering
> intermedio.

### 3. Frontend a Firebase Hosting (o Cloud Run)

```bash
cd frontend
echo "VITE_API_BASE=https://nutricoach-backend-xxxx-uc.a.run.app" > .env.production
npm run build

# Opción A: Firebase Hosting
firebase init hosting
firebase deploy --only hosting

# Opción B: Cloud Run con Nginx
# (ver frontend/Dockerfile si lo agregás)
```

## 🧪 Smoke test post-deploy

```bash
BASE=https://tu-backend.run.app

curl $BASE/health
# {"status":"ok"}

curl $BASE/clients
# Lista de 3 clientes

# Stream test (Ctrl+C para cortar)
curl -N "$BASE/agent/stream?client_id=client_001&message=Hola%2C+%C2%BFqu%C3%A9+puedo+desayunar+hoy%3F"
```

## 🐛 Troubleshooting

| Síntoma | Causa probable | Fix |
|---|---|---|
| `Firestore: index not found` | Falta índice `client_id ASC, updated_at DESC` en `conversations` | Crear con el link que da el error |
| Tokens llegan todos juntos | Proxy buffereando | Verificar header `X-Accel-Buffering: no` (ya está) |
| `429 rate limit exceeded` | El rate limiter hizo lo suyo | Esperar 60s. Para tests intensivos, subir `_RATE_MAX_REQS` |
| `400 rejected: empty_message` | El frontend envió string vacío | Validar input antes de hacer fetch |
| El agente nunca usa USDA | Docstring poco clara | Revisar `tools_langchain.py`, agregar más ejemplos del dominio |
| Costo se va de las manos | Routing forzando siempre `gpt-5` | Loguear `routing.reason` en Cloud Logging y ajustar heurísticas |

## 📊 Métricas a monitorear

Cloud Logging queries útiles:

```
# Distribución de tier de modelo
jsonPayload.message =~ "routing client_id" | summarize count by jsonPayload.model

# Latencia P95
resource.type = "cloud_run_revision" | latency.p95

# Errores de extracción de facts
jsonPayload.message =~ "fact_extraction_(parse|llm)_error"
```

## 📜 Licencia y créditos

- USDA FoodData Central data: dominio público (CC0).
- Proyecto educativo BSG Institute.
