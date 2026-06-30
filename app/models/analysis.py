from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    incident_id: int
    title: str
    description: str
    severity: str
    namespace: str = "default"
    deployment_name: str
    service_name: Optional[str] = None


class AnalyzeResponse(BaseModel):
    summary: str
    probable_root_cause: str
    evidence: List[str]
    recommended_actions: List[str]
    suggested_kubectl_commands: List[str]
    confidence: int
    diagnostics: Optional[Dict[str, Any]] = None