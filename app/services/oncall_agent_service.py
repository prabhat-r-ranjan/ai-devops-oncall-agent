from app.models.analysis import AnalyzeRequest, AnalyzeResponse
from app.clients.kubernetes_client import KubernetesClient


class OnCallAgentService:

    def __init__(self):
        self.kubernetes_client = KubernetesClient()

    def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        diagnostics = self.kubernetes_client.get_deployment_diagnostics(
            namespace=request.namespace,
            deployment_name=request.deployment_name
        )

        return AnalyzeResponse(
            summary=f"Incident '{request.title}' received for analysis.",
            probable_root_cause="Kubernetes diagnostics collected. Rule-based root cause analysis will be added next.",
            evidence=[
                f"Namespace: {request.namespace}",
                f"Deployment: {request.deployment_name}",
                f"Severity: {request.severity}",
                f"Diagnostics collected for deployment: {request.deployment_name}"
            ],
            recommended_actions=[
                "Review pod restart count",
                "Check recent Kubernetes events",
                "Check application logs",
                "Verify deployment readiness"
            ],
            suggested_kubectl_commands=[
                f"kubectl get pods -n {request.namespace}",
                f"kubectl describe deployment {request.deployment_name} -n {request.namespace}",
                f"kubectl get events -n {request.namespace} --sort-by=.lastTimestamp",
                f"kubectl logs -n {request.namespace} -l app={request.deployment_name} --tail=100"
            ],
            confidence=70,
            diagnostics=diagnostics
        )