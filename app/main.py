from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="TG Audit Orchestrator",
    version="0.1.0",
    description="Compliance and security audit management platform",
)

app.mount("/static", StaticFiles(directory="app/web/static"), name="static")


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}
