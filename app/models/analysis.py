from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    incident_id: str
    title: str
    description: str
    severity: str
    namespace: str
    deployment_name: str
    service_name: Optional[str] = None


class AnalyzeResponse(BaseModel):
    summary: str
    primary_issue: Optional[str] = None
    probable_root_cause: str
    evidence: List[str]
    recommended_actions: List[str]
    suggested_kubectl_commands: List[str]
    confidence: int
    diagnostics: Dict[str, Any]

    rule_fix_plan: Optional[Dict[str, Any]] = None
    ai_fix_plan: Optional[Dict[str, Any]] = None
    fix_plan: Optional[Dict[str, Any]] = None

    repository_analysis: Optional[Dict[str, Any]] = None
    manifest_update: Optional[Dict[str, Any]] = None
    pull_request: Optional[Dict[str, Any]] = None