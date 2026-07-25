from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers.auth import router as auth_router
from app.user_store import store


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.load()
    if settings.jwt_secret == "dev-only-insecure-secret-change-me-via-JWT_SECRET-env-var":
        print(
            "WARNING: auth-service is running with the insecure default JWT_SECRET. "
            "Set the JWT_SECRET env var before any real deployment - see README.md."
        )
    yield


app = FastAPI(
    title="Crime Intelligence Platform - Auth Service",
    description=(
        "Secure RBAC / governance (pillar 10): JWT-based login, three roles "
        "(ANALYST / INVESTIGATOR / ADMIN), and an audit log of login attempts and "
        "access-denied events. Other services verify tokens issued here statelessly "
        "(same shared secret, no callback per request) - see "
        "backend/services/offender-profiling/app/rbac.py for the pattern applied "
        "to one service end to end."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# The one service in this platform that needs POST - credentials must never
# travel in a URL/query string (server/proxy access logs would capture them),
# so login is a POST with a JSON body, unlike every GET-only analytics service.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.get("/health")
def health():
    return {"status": "ok", "users_loaded": len(store.users_by_username)}
