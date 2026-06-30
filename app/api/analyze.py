from fastapi import APIRouter
from app.models.analysis import AnalyzeRequest, AnalyzeResponse
from app.services.oncall_agent_service import OnCallAgentService

router = APIRouter()
service = OnCallAgentService()


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest):
    return service.analyze_incident(request)