from app.clients.kubernetes_client import KubernetesClient
from app.services.rule_based_rca_engine import RuleBasedRcaEngine


class OnCallAgentService:
    def __init__(self):
        self.kubernetes_client = KubernetesClient()
        self.rca_engine = RuleBasedRcaEngine()

    def analyze_incident(self, request):
        diagnostics = self.kubernetes_client.collect_diagnostics(
            namespace=request.namespace,
            deployment_name=request.deployment_name,
            service_name=request.service_name,
        )

        return self.rca_engine.analyze(diagnostics)