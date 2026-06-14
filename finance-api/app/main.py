from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401 - registers all models on Base.metadata
from app.api.routes import auth, categories, debts, stats, transactions
from app.database import Base, engine

# For the diploma demo we auto-create tables on startup.
# In production this is replaced by Alembic migrations.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Personal Finance API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(categories.router)
app.include_router(transactions.router)
app.include_router(debts.router)
app.include_router(stats.router)


@app.get("/", tags=["root"])
def root():
    return {"status": "ok", "docs": "/docs"}
