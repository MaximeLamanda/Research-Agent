# Research Agent

Agent de recherche autonome pour installateur solaire C&I. Parcourt chaque semaine des articles de construction (industriel, logistique, retail) par département, extrait des fiches projet et les agrège.

## Stack

- **Backend:** Python, FastAPI, PostgreSQL, Exa.ai, Vercel AI Gateway
- **Frontend:** Next.js, shadcn/ui

## Démarrage local

```bash
cp .env.example .env
# Renseigner EXA_API_KEY, AI_GATEWAY_API_KEY
# AI_MODEL=deepseek/deepseek-v4-flash (défaut)

# Option A — Docker (recommandé)
docker compose up --build

# Option B — Sans Docker
cd backend && pip install -e ".[dev]"
DATABASE_URL="sqlite:///./research.db" uvicorn app.main:app --reload --port 8001

# Terminal 2
cd frontend && npm install && npm run dev
```

> **Note :** si le port 8000 est déjà utilisé, lancez le backend sur `8001` et mettez `NEXT_PUBLIC_API_URL=http://localhost:8001` dans `.env`.

- Frontend : http://localhost:3000
- API : http://localhost:8001 (ou 8000 via Docker)

## Documentation

- [Design](docs/plans/2026-06-16-research-agent-design.md)
- [Plan d'implémentation](docs/plans/2026-06-16-research-agent.md)
