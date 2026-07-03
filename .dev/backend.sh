#!/usr/bin/env bash
cd "/Users/maximelamanda/Research-Agent/backend"
export DATABASE_URL="sqlite:////Users/maximelamanda/Research-Agent/backend/research.db"
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
