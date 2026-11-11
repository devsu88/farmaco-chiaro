"""FastAPI app per Farmaco Chiaro."""
from __future__ import annotations

import logging

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import farmaci
from app.config import FRONTEND_ORIGINS
from app.routes import chat, rag, search, simplify, tts
from app.routes import farmaci as farmaci_routes
from app.routes import scenari as scenari_routes
from services import vector_store

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Farmaco Chiaro API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.include_router(farmaci_routes.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(simplify.router, prefix="/api")
app.include_router(tts.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(scenari_routes.router, prefix="/api")
app.include_router(rag.router, prefix="/api")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    logger.exception("Errore non gestito su %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Errore interno del servizio",
            }
        },
    )


@app.get("/")
def root() -> dict:
    return {"status": "ok", "service": "farmaco-chiaro-backend"}


@app.get("/health")
def health() -> dict:
    return {"status": "healthy"}


@app.get("/ready")
def ready():
    """Readiness: registro, artefatti e (non bloccante) Qdrant."""
    try:
        mancanti = farmaci.valida_file()
        if mancanti:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "error": "Artefatti RAG mancanti",
                    "dettagli": mancanti,
                },
            )
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "error": str(exc)},
        )
    return {
        "status": "ready",
        "farmaci": len(farmaci.all()),
        "qdrant": vector_store.is_available(),
    }
