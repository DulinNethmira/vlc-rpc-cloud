from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine
import models

# In a pure production scenario, alembic should handle the creation,
# but for local dev with SQLite we can just create them if they don't exist.
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="VLC RPC Cloud API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok"}

from telemetry import router as telemetry_router
from auth_router import router as auth_router
from fastapi.staticfiles import StaticFiles
import os

app.include_router(telemetry_router)
app.include_router(auth_router)

# Mount admin dashboard
admin_dir = os.path.join(os.path.dirname(__file__), "admin")
if os.path.exists(admin_dir):
    app.mount("/admin", StaticFiles(directory=admin_dir, html=True), name="admin")
