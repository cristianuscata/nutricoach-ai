# CLAUDE.md — Guía de Ejecución para Claude Code

> **Para Claude Code**: Este archivo es tu guía operativa para llevar este
> proyecto desde el estado actual hasta una entrega completa con URL pública.
> Sigue las fases en orden. Al final de cada fase hay un **criterio de
> aceptación** verificable. No avances a la siguiente fase si la actual falla.

---

## 0. Contexto del proyecto

### 0.1 Qué es NutriCoach

Asistente conversacional de nutrición personalizada (proyecto final del curso
de **BSG Institute · Agentes de IA con Memoria Persistente**). Combina:

- Perfiles médico-nutricionales en Firestore (3 clientes de prueba)
- Memoria persistente entre sesiones (mensajes + facts semánticos)
- Búsqueda en tiempo real (USDA FoodData Central + Tavily)
- Streaming SSE de tokens del LLM
- Frontend React + Vite

### 0.2 Stack confirmado

| Capa | Tecnología |
|---|---|
| Backend | FastAPI 0.135 + Python 3.11+ |
| Agente | LangChain Classic + langchain-openai |
| LLM | OpenAI `gpt-5-mini` (default) ↔ `gpt-5` (router) |
| DB | Firestore (3 colecciones: `clients`, `conversations`, `client_facts`) |
| Tools | USDA FoodData Central (primaria), Tavily (secundaria) |
| Streaming | sse-starlette con heartbeats |
| Frontend | React 18 + Vite 5, sin librerías de UI (CSS custom) |
| Deploy | Cloud Run (backend) + Firebase Hosting o Cloud Run (frontend) |

### 0.3 Archivos ya entregados (deberían estar en el workspace)

```
nutricoach/
├── CASO_DE_USO.md
├── README.md
├── .gitignore
├── backend/
│   ├── .env.example
│   ├── Dockerfile
│   ├── config.py
│   ├── firestore.rules
│   ├── main.py
│   ├── requirements.txt
│   ├── schemas.py
│   ├── seed.py
│   ├── agent/
│   │   ├── agent.py
│   │   ├── model_router.py
│   │   └── tools_langchain.py
│   ├── data/
│   │   └── seed_clients.json
│   ├── firebase/
│   │   ├── client.py
│   │   ├── clients.py
│   │   ├── chat_history.py
│   │   └── long_term_memory.py
│   ├── routers/
│   │   ├── agent_router.py
│   │   └── clients_router.py
│   ├── security/
│   │   └── guardrails.py
│   └── tools/
│       └── nutrition_tools.py
└── frontend/
    ├── .env.example
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── App.jsx
        ├── api.js
        ├── main.jsx
        └── styles.css
```

### 0.4 Tu rol como Claude Code

- Eres el ejecutor. El usuario puede no tener experiencia en cada paso.
- Antes de cada fase, **lee los archivos relevantes** con `view` para
  asegurarte que el estado del repo coincide con lo esperado.
- Los archivos `__init__.py` no se generaron explícitamente. Si Python falla
  con "No module named X", crea `backend/agent/__init__.py`,
  `backend/firebase/__init__.py`, etc., como archivos vacíos.
- **Nunca commitees** `.env`, `firebase-service-account.json`, ni `node_modules/`.
- Usa Python 3.11+ y Node 18+. Si `python` apunta a una versión menor, usa
  `python3.11` o `python3` explícitamente.

---

## Fase 1 — Validar archivos faltantes

### 1.1 Tarea

Verificar que existen todos los archivos listados en 0.3. Si **alguno falta**,
créalo. Para los del backend que ya describí en `README.md`, generalo a partir
del contenido descrito (ya está documentado en cada archivo).

### 1.2 Verificación

```bash
cd nutricoach
ls backend/agent/ backend/firebase/ backend/routers/ backend/security/ backend/tools/
ls frontend/src/
```

Esperado: cada directorio listado en 0.3 debe tener los archivos indicados.

### 1.3 Crear `__init__.py` faltantes (si Python los pide después)

```bash
cd backend
touch agent/__init__.py firebase/__init__.py routers/__init__.py security/__init__.py tools/__init__.py
```

### ✅ Criterio de aceptación

`find backend -name "*.py" | wc -l` devuelve **al menos 13** archivos `.py`.

---

## Fase 2 — Servicios externos (manual del usuario)

⚠️ **Esta fase requiere intervención humana.** Pídele al usuario que ejecute
los pasos y te confirme cuando termine. No puedes automatizar la creación
de cuentas.

### 2.1 Firebase

1. El usuario va a [console.firebase.google.com](https://console.firebase.google.com)
   y crea un nuevo proyecto. **Anota el `Project ID`** (no el nombre).
2. **Build → Firestore Database → Create database** → modo producción → región
   `us-central1` (o la más cercana a Lima/Perú).
3. **Project Settings → Service accounts → Generate new private key**.
   Descarga el JSON.
4. Renombrar el archivo a `firebase-service-account.json` y colocarlo en
   `backend/firebase-service-account.json`.
5. **Crear el índice compuesto** (esto se puede hacer ahora o esperar al primer
   error en runtime, que da un link de un click):
   - Firestore → Indexes → Add index
   - Collection: `conversations`
   - Fields: `client_id` Ascending, `updated_at` Descending
   - Query scope: Collection

### 2.2 OpenAI

1. [platform.openai.com](https://platform.openai.com) → API keys → Create new secret key.
2. Asegurar que la cuenta tenga **mínimo $5 USD** de saldo.
3. Confirmar que la cuenta tiene acceso a los modelos `gpt-5-mini` y `gpt-5`.
   Si no, modificar `backend/agent/model_router.py` línea ~37 para usar
   `gpt-4o-mini` y `gpt-4o` como fallback (y actualizar las descripciones de
   costo en los comentarios).

### 2.3 Tavily

1. [tavily.com](https://tavily.com) → registro → dashboard → copiar API key.

### 2.4 USDA FoodData Central

1. [fdc.nal.usda.gov/api-key-signup](https://fdc.nal.usda.gov/api-key-signup/)
2. Llenar form, recibir key por email.
3. Si el usuario quiere saltarse esto al inicio, puede usar `DEMO_KEY` con
   rate limit muy bajo (30 req/h) — bastante para los primeros tests.

### ✅ Criterio de aceptación

El usuario te confirma que tiene **4 valores** en mano:
- Firebase project ID
- Path al `firebase-service-account.json`
- OpenAI API key
- Tavily API key
- USDA API key (o `DEMO_KEY`)

---

## Fase 3 — Setup local del backend

### 3.1 Crear `.env`

```bash
cd backend
cp .env.example .env
```

Edita `backend/.env` y completa con los valores de la Fase 2:

```
OPENAI_API_KEY=sk-proj-...
TAVILY_API_KEY=tvly-...
USDA_API_KEY=...   # o DEMO_KEY
GOOGLE_APPLICATION_CREDENTIALS=./firebase-service-account.json
FIREBASE_PROJECT_ID=...
CORS_ORIGINS=http://localhost:5173
LOG_LEVEL=INFO
```

### 3.2 Entorno virtual e instalación de deps

```bash
cd backend
python3.11 -m venv venv      # o python -m venv venv
source venv/bin/activate     # Linux/Mac
# venv\Scripts\activate      # Windows
pip install --upgrade pip
pip install -r requirements.txt
```

**Posibles errores:**

- `ERROR: Could not find a version that satisfies the requirement langchain==1.2.13`:
  el ecosistema LangChain cambia rápido. Si la versión exacta no está
  disponible, ejecuta:
  ```bash
  pip install "langchain>=0.3,<1.3" "langchain-openai>=0.2" "langchain-core>=0.3" "sse-starlette>=2.2" \
              firebase-admin tavily-python httpx cachetools fastapi "uvicorn[standard]" \
              pydantic-settings python-dotenv
  ```
  Y actualiza `requirements.txt` con `pip freeze > requirements.txt`.

- `ImportError: No module named 'langchain_classic'`: en versiones recientes
  de langchain este nombre cambió. Si pasa, edita `backend/agent/agent.py`:
  ```python
  # Reemplazar:
  from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
  # Por:
  from langchain.agents import AgentExecutor, create_openai_tools_agent
  ```

### 3.3 Cargar perfiles iniciales

```bash
python seed.py
```

Esperado:
```
📥 Cargando seed_clients.json...
  ✅ client_001 — Ana Torres
  ✅ client_002 — Marco Rivera
  ✅ client_003 — Lucía Pérez
✨ Listo. 3 clientes en Firestore.
```

### 3.4 Levantar el servidor

```bash
uvicorn main:app --reload --port 8000
```

### ✅ Criterio de aceptación (verifica vía curl)

```bash
curl http://localhost:8000/health
# {"status":"ok"}

curl http://localhost:8000/clients | python -m json.tool
# Debe listar 3 clientes (Ana, Marco, Lucía)
```

Si ambos pasan, la fase está completa.

---

## Fase 4 — Setup del frontend

### 4.1 Instalar deps

```bash
cd frontend
npm install
```

### 4.2 Levantar dev server

```bash
npm run dev
```

Vite imprime: `Local:   http://localhost:5173/`

### 4.3 Smoke test manual

1. Abre `http://localhost:5173`.
2. Debe verse el sidebar con 3 clientes (Ana, Marco, Lucía).
3. Click en Ana → aparece la barra de perfil con sus chips (objetivos +
   restricciones).
4. Escribe "Hola, ¿qué desayuno me recomiendas?" → enviar.
5. Deben llegar tokens en streaming. La respuesta debe mencionar a Ana por
   nombre y respetar su intolerancia a la lactosa.

### ✅ Criterio de aceptación

- [ ] La página carga sin errores en consola del navegador.
- [ ] Los 3 clientes aparecen en el sidebar.
- [ ] Al enviar un mensaje, aparece el badge `gpt-5-mini · default_simple_chat`
      bajo el composer (esto valida que el model router está activo).
- [ ] La respuesta llega en streaming (tokens visibles uno a uno).
- [ ] La respuesta menciona el nombre o algún dato del perfil.

---

## Fase 5 — Verificación de los 3 pilares del proyecto

Esto es lo que el evaluador busca. Debe quedar **grabable en video** o
**reproducible en URL pública**.

### 5.1 Pilar 1: Personalización con datos reales del perfil

Con cliente **Lucía Pérez** seleccionada, pregunta:
> "¿Qué puedo desayunar mañana?"

**Esperado**: la respuesta debe considerar (sin que tú lo menciones) que es
vegana, está embarazada en segundo trimestre, tiene anemia leve, y le gusta
la cocina mediterránea/india. Si el agente sugiere algo no-vegano, el
proyecto falla. Si solo dice "un desayuno saludable", el proyecto falla.

### 5.2 Pilar 2: Búsqueda en tiempo real (tool use)

Con cualquier cliente, pregunta:
> "¿Cuántas calorías y cuánta proteína tiene la palta cruda?"

**Esperado**:
- Debe aparecer el indicador "Consultando USDA FoodData Central".
- El badge del modelo debe cambiar a `gpt-5 · tool_hint_match` (el router
  escala porque detectó "calorías"/"proteína").
- La respuesta cita números concretos y la fuente USDA.

### 5.3 Pilar 3: Memoria persistente

1. Con cliente **Ana**, envía 2-3 mensajes con contenido reportable
   (ej. "Acabo de comer arroz con pollo y me sentí pesada después").
2. Cierra la pestaña del navegador.
3. Espera ~30 segundos (para que la background task de extracción de facts
   complete — verifica en logs del backend).
4. Vuelve a abrir `http://localhost:5173`, selecciona Ana de nuevo.
5. La conversación previa debe estar restaurada.
6. Inicia una **conversación nueva** con "Recordatorio del último síntoma
   que te conté".
7. **Esperado**: el agente debe recordar la pesadez con el arroz, **aunque
   esté en una conversación nueva** (esto demuestra la memoria de largo plazo
   vía `client_facts`, no solo el array de mensajes).

### ✅ Criterio de aceptación

Los tres pilares funcionan en orden. Si cualquiera falla, debug antes de
avanzar:

- **Falla pilar 1**: revisar `backend/agent/agent.py` línea del system prompt.
  Verificar que `client_profile_json` incluye los datos.
- **Falla pilar 2**: revisar `backend/agent/tools_langchain.py`, las docstrings
  de `@tool` deben ser específicas. Revisar logs del backend para ver si la
  tool se invocó.
- **Falla pilar 3**: revisar logs del backend filtrando por
  `fact_extraction_saved`. Si nunca aparece, hay un error en
  `backend/firebase/long_term_memory.py`.

---

## Fase 6 — Deploy a Cloud Run (URL pública)

El usuario marcó este paso como crítico. Vamos en orden.

### 6.1 Pre-requisitos

```bash
# Instalar gcloud CLI si no está
gcloud --version

# Autenticar
gcloud auth login
gcloud auth application-default login

# Configurar proyecto (mismo que Firebase)
gcloud config set project TU_PROJECT_ID

# Habilitar APIs necesarias
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable artifactregistry.googleapis.com
```

### 6.2 Subir secretos a Secret Manager

```bash
cd backend

# Service account de Firebase
gcloud secrets create firebase-sa --data-file=firebase-service-account.json

# API keys (lee del .env)
source .env
echo -n "$OPENAI_API_KEY" | gcloud secrets create openai-key --data-file=-
echo -n "$TAVILY_API_KEY" | gcloud secrets create tavily-key --data-file=-
echo -n "$USDA_API_KEY"   | gcloud secrets create usda-key   --data-file=-
```

### 6.3 Build y deploy del backend

```bash
PROJECT_ID=$(gcloud config get-value project)
REGION=us-central1

# Build de la imagen
gcloud builds submit . --tag gcr.io/$PROJECT_ID/nutricoach-backend

# Deploy a Cloud Run
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
  --set-env-vars "FIREBASE_PROJECT_ID=$PROJECT_ID,GOOGLE_APPLICATION_CREDENTIALS=/secrets/firebase-sa.json,LOG_LEVEL=INFO,CORS_ORIGINS=http://localhost:5173" \
  --set-secrets "/secrets/firebase-sa.json=firebase-sa:latest,OPENAI_API_KEY=openai-key:latest,TAVILY_API_KEY=tavily-key:latest,USDA_API_KEY=usda-key:latest"
```

Al final, gcloud imprime: `Service URL: https://nutricoach-backend-xxxx-uc.a.run.app`. **Anótala**.

### 6.4 Verificar el backend desplegado

```bash
BACKEND_URL=https://nutricoach-backend-xxxx-uc.a.run.app  # tu URL real

curl $BACKEND_URL/health
# {"status":"ok"}

curl $BACKEND_URL/clients
# Lista de 3 clientes
```

### 6.5 Build y deploy del frontend

**Opción A — Firebase Hosting (recomendada, gratis y rápida)**:

```bash
cd ../frontend

# Configurar la URL del backend
echo "VITE_API_BASE=https://nutricoach-backend-xxxx-uc.a.run.app" > .env.production

# Build
npm run build
# Genera carpeta `dist/`

# Firebase Hosting
npm install -g firebase-tools  # si no está
firebase login
firebase init hosting
# - Use existing project → seleccionar el mismo de Firebase
# - Public directory: dist
# - Single-page app: Yes
# - Set up automatic builds: No

firebase deploy --only hosting
# Imprime: Hosting URL: https://TU_PROJECT_ID.web.app
```

**Opción B — Cloud Run con servidor estático** (si prefieres todo en un solo lugar):

Crea `frontend/Dockerfile`:

```dockerfile
FROM node:18-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

Y `frontend/nginx.conf`:
```
server {
  listen 8080;
  root /usr/share/nginx/html;
  location / { try_files $uri /index.html; }
}
```

Build y deploy:
```bash
gcloud builds submit . \
  --tag gcr.io/$PROJECT_ID/nutricoach-frontend \
  --substitutions=_VITE_API_BASE=$BACKEND_URL

gcloud run deploy nutricoach-frontend \
  --image gcr.io/$PROJECT_ID/nutricoach-frontend \
  --platform managed --region $REGION \
  --allow-unauthenticated --port 8080
```

### 6.6 Actualizar CORS del backend

Una vez tengas la URL del frontend, actualiza CORS:

```bash
gcloud run services update nutricoach-backend \
  --region $REGION \
  --update-env-vars "CORS_ORIGINS=https://TU_PROJECT_ID.web.app,http://localhost:5173"
```

### ✅ Criterio de aceptación

- [ ] La URL del frontend (`https://TU_PROJECT_ID.web.app`) carga la app.
- [ ] El sidebar muestra los 3 clientes.
- [ ] Una conversación de prueba funciona end-to-end con streaming.
- [ ] Los 3 pilares de la Fase 5 funcionan también en producción.

---

## Fase 7 — Entrega

### 7.1 Repositorio en GitHub

```bash
cd ..  # raíz del proyecto
git init
git add .
git status   # ⚠️ verifica que .env y firebase-service-account.json NO aparezcan
git commit -m "feat: NutriCoach — asistente nutricional con memoria persistente"
git branch -M main
gh repo create nutricoach --public --source=. --remote=origin --push
# o crear repo manualmente y luego:
# git remote add origin git@github.com:TU_USER/nutricoach.git
# git push -u origin main
```

### 7.2 Verificar que NO se subieron credenciales

```bash
# Si alguno de estos comandos imprime algo, ABORTA y rota las keys
git ls-files | grep -E '\.env$|firebase-service-account\.json'
```

Si aparecen archivos sensibles:
```bash
git rm --cached backend/.env backend/firebase-service-account.json
echo "backend/.env" >> .gitignore
echo "backend/firebase-service-account.json" >> .gitignore
git commit -am "fix: exclude credentials"
# Y rotar las keys en cada proveedor.
```

### 7.3 Video demostrativo (Opción A del entregable)

Graba con OBS, Loom o el grabador de pantalla del SO. Mínimo 3 minutos.
Sigue exactamente este script:

1. **0:00–0:30** — Abrir la URL pública. Mostrar el sidebar con los 3 clientes.
2. **0:30–1:15** — Seleccionar **Ana**. Mostrar que el chip "lactose intolerant"
   aparece en el perfil. Escribir: *"Estoy en oficina, ¿qué snack a media tarde
   me recomiendas?"*. Mostrar streaming.
3. **1:15–2:15** — Seleccionar **Marco** (keto). Preguntar: *"¿Cuántas calorías
   y carbs tiene 100g de palta? ¿me sirve para mi dieta?"*. Mostrar el badge
   `gpt-5 · tool_hint_match` y el indicador "Consultando USDA". Resaltar la
   diferencia entre los dos clientes.
4. **2:15–3:00** — **Cerrar la pestaña**. Reabrir la URL. Seleccionar Marco
   otra vez. Mostrar que el historial se restauró. Iniciar una conversación
   nueva (botón "+ Nueva") y preguntar: *"¿Qué te conté que estaba haciendo
   esta semana?"*. El agente debe recordar (por la memoria de largo plazo).
5. **3:00+** — Mostrar Cloud Run dashboard con la URL pública activa.

### 7.4 Submit final

Reúne en un email/form al instructor:

- ✉️ URL pública del frontend
- ✉️ URL pública del backend (`/health`)
- ✉️ URL del repo en GitHub
- ✉️ Link al video (si aplica)
- ✉️ El archivo `CASO_DE_USO.md` (ya está en el repo)

### ✅ Criterio de aceptación final

Checklist del PDF:

- [x] CASO_DE_USO.md presente
- [x] 3 perfiles ricos
- [x] System prompt personalizado
- [x] Tool funcional (USDA + Tavily)
- [x] Backend en Cloud Run sin errores
- [x] Frontend en Firebase Hosting
- [x] Conversaciones persisten al recargar
- [x] README con instrucciones
- [x] `.env` y `firebase-service-account.json` NO en repo
- [x] Video o URL pública
- [x] **(BONUS)** Despliegue en la nube

---

## Apéndice A — Troubleshooting rápido

| Síntoma | Causa | Fix |
|---|---|---|
| `firestore: requires an index` | Falta índice compuesto | Click en el link del error → crear índice |
| `Module not found: langchain_classic` | Versión nueva de langchain | Usar `from langchain.agents import ...` |
| `403 forbidden` al levantar Cloud Run | Falta `--allow-unauthenticated` | Re-deploy con el flag |
| Tokens no llegan en streaming en producción | Buffering del proxy | Verificar header `X-Accel-Buffering: no` (ya en el código) |
| `429 rate limit` | El rate limiter del backend | Esperar 60s o subir `_RATE_MAX_REQS` |
| El agente nunca usa USDA | Docstring débil | Agregar más ejemplos a `tools_langchain.py` |
| CORS error en producción | URL del frontend no en CORS | Update env var `CORS_ORIGINS` |
| Memoria larga no funciona | Background task falla silenciosa | Buscar `fact_extraction_*` en Cloud Logging |
| `gpt-5-mini does not exist` | La cuenta no tiene acceso al modelo | Cambiar a `gpt-4o-mini` y `gpt-4o` en `model_router.py` |

## Apéndice B — Comandos útiles post-deploy

```bash
# Logs del backend
gcloud run services logs read nutricoach-backend --region us-central1 --limit 100

# Métricas de costo OpenAI
# En Cloud Logging, filtra:
jsonPayload.message =~ "routing client_id"

# Reiniciar el servicio (forzar pull de imagen)
gcloud run services update nutricoach-backend --region us-central1

# Ver secretos (sin revelar valor)
gcloud secrets list

# Borrar todo (cleanup)
gcloud run services delete nutricoach-backend --region us-central1
gcloud run services delete nutricoach-frontend --region us-central1
firebase hosting:disable
```

## Apéndice C — Variables de entorno completas

### Backend (`backend/.env` en local, env vars en Cloud Run)

| Var | Local | Cloud Run |
|---|---|---|
| `OPENAI_API_KEY` | valor directo | secret `openai-key` |
| `TAVILY_API_KEY` | valor directo | secret `tavily-key` |
| `USDA_API_KEY` | valor directo o `DEMO_KEY` | secret `usda-key` |
| `GOOGLE_APPLICATION_CREDENTIALS` | `./firebase-service-account.json` | `/secrets/firebase-sa.json` |
| `FIREBASE_PROJECT_ID` | tu project id | tu project id |
| `CORS_ORIGINS` | `http://localhost:5173` | `https://TU_PROJECT_ID.web.app,http://localhost:5173` |
| `LOG_LEVEL` | `INFO` | `INFO` |

### Frontend (`frontend/.env.production`)

| Var | Valor |
|---|---|
| `VITE_API_BASE` | URL pública del backend (ej. `https://nutricoach-backend-xxxx-uc.a.run.app`) |
