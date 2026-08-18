from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import close_driver, init_constraints
from app.routers import claims, reference
from app.seed_data import seed

app = FastAPI(title="Hospital Claims Integrity Platform", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(claims.router)
app.include_router(reference.router)


@app.on_event("startup")
def on_startup():
    init_constraints()
    seed()


@app.on_event("shutdown")
def on_shutdown():
    close_driver()


@app.get("/api/health")
def health():
    return {"status": "ok"}
