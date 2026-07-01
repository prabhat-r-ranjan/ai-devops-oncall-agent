from fastapi import FastAPI
from app.api.analyze import router as analyze_router
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

app = FastAPI(
    title="AI DevOps On-Call Agent",
    version="1.0.0",
    description="AI Agent for Kubernetes Incident Investigation"
)


@app.get("/")
def root():
    return {"message": "AI DevOps On-Call Agent is running"}


@app.get("/health")
def health():
    return {"status": "UP", "service": "ai-devops-oncall-agent"}


app.include_router(analyze_router)