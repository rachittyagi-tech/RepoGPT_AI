"""
app/api/v1/router.py

Aggregates all v1 routers into a single `api_router` that `main.py`
mounts under `settings.API_V1_PREFIX`. Future domain routers (auth,
repositories, chat, rag) get included here — `main.py` never needs
to change when new v1 endpoints are added (Open/Closed Principle).
"""

from fastapi import APIRouter

from app.api.v1.system import router as system_router

api_router = APIRouter()
api_router.include_router(system_router)

# Future (Step 3+):
# from app.api.v1.auth import router as auth_router
# from app.api.v1.repositories import router as repositories_router
# api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
# api_router.include_router(repositories_router, prefix="/repositories", tags=["Repositories"])
