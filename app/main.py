from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.analyze import router as analyze_router
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="AI DevOps On-Call Agent",
    version="1.0.0",
    description="AI Agent for Kubernetes Incident Investigation"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "AI DevOps On-Call Agent is running"}


@app.get("/health")
def health():
    return {"status": "UP", "service": "ai-devops-oncall-agent"}


app.include_router(analyze_router)