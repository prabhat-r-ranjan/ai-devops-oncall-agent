"""
API layer for incident analysis.

This file only exposes REST endpoints.
Business logic is handled by OnCallAgentService.
"""

from fastapi import APIRouter

from app.models.analysis import AnalyzeRequest, AnalyzeResponse
from app.services.oncall_agent_service import OnCallAgentService


router = APIRouter()
service = OnCallAgentService()


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest):
    """
    Analyze an incident.

    Flow:
    1. Receive incident details from API request.
    2. Delegate work to OnCallAgentService.
    3. Return RCA response.
    """
    return service.analyze_incident(request)