"""
Two health endpoints, because Kubernetes asks two different questions:

- /health/live  "Is the process alive?" Cheap, no dependencies. If this
  fails, restarting the container could help.
- /health       "Can this instance serve requests?" Checks ChromaDB,
  the cache store and the user database. If a dependency is down this
  returns 503, so traffic goes elsewhere - but restarting the API
  wouldn't fix it, which is why liveness doesn't check them.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.db import connect
from app.services import cache, retrieval

router = APIRouter()


def _check_chroma():
    retrieval.get_collection().count()


def _check_cache():
    cache.store.ping()


def _check_database():
    with connect() as conn:
        conn.execute("SELECT 1")


CHECKS = {"chroma": _check_chroma, "cache": _check_cache, "database": _check_database}


@router.get("/live")
def live():
    return {"status": "ok"}


@router.get("")
def ready():
    results = {}
    for name, check in CHECKS.items():
        try:
            check()
            results[name] = "ok"
        except Exception as e:
            results[name] = f"error: {type(e).__name__}"
    healthy = all(r == "ok" for r in results.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ok" if healthy else "unavailable", "checks": results},
    )
