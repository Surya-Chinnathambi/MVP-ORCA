from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.api import (
    auth, users, roles, permissions,
    clients, projects, scope, approvals,
    methodology, requirements, tasks, evidence_requests, evidence_items, findings, gates,
    deliverables, packs,
)
from app.api import workmode, security, notifications, agents
from app.web.router import router as web_router

app = FastAPI(
    title="TG Audit Orchestrator",
    version="0.1.0",
    description="Compliance and security audit management platform",
)

app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, https_only=False)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(roles.router)
app.include_router(permissions.router)
app.include_router(clients.router)
app.include_router(projects.router)
app.include_router(scope.router)
app.include_router(approvals.router)
app.include_router(methodology.router)
app.include_router(requirements.router)
app.include_router(tasks.router)
app.include_router(evidence_requests.router)
app.include_router(evidence_items.router)
app.include_router(findings.router)
app.include_router(gates.router)
app.include_router(deliverables.router)
app.include_router(packs.router)
app.include_router(workmode.router)
app.include_router(security.router)
app.include_router(notifications.router)
app.include_router(agents.router)
app.include_router(web_router)

app.mount("/static", StaticFiles(directory="app/web/static"), name="static")


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}
