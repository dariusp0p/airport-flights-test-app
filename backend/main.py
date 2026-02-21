from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router as api_router

app = FastAPI(
    title="Flight Delay Predictor API",
    version="0.1.0",
)

# For dev: allow frontend(s) to call your backend.
# In prod, restrict origins to your deployed domains.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # change later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

@app.get("/health")
def health():
    return {"ok": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", reload=True)
