from fastapi import FastAPI

app = FastAPI(
    title="AI DevOps On-Call Agent",
    version="1.0.0",
    description="AI Agent for Kubernetes Incident Investigation"
)


@app.get("/")
def root():
    return {
        "message": "AI DevOps On-Call Agent is running"
    }


@app.get("/health")
def health():
    return {
        "status": "UP",
        "service": "ai-devops-oncall-agent"
    }


@app.post("/analyze")
def analyze():
    return {
        "summary": "MVP is working",
        "probableRootCause": "No issue detected",
        "confidence": 100
    }