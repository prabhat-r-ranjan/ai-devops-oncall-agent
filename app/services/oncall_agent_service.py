"""
Main orchestration service for the AI DevOps On-Call Agent.

Workflow:
1. Collect Kubernetes diagnostics.
2. Run rule-based RCA.
3. Generate FixPlan using GitAnalyzer.
4. Return final response.
"""

from app.clients.kubernetes_client import KubernetesClient
from app.services.rule_based_rca_engine import RuleBasedRcaEngine
from app.services.git_analyzer import GitAnalyzer


class OnCallAgentService:
    """
    Coordinates incident analysis across Kubernetes, RCA, and Git analysis.
    """

    def __init__(self):
        """
        Initialize service dependencies.
        """
        self.kubernetes_client = KubernetesClient()
        self.rca_engine = RuleBasedRcaEngine()
        self.git_analyzer = GitAnalyzer()

    def analyze_incident(self, request):
        """
        Analyze one incident request.

        Steps:
        1. Collect Kubernetes diagnostics.
        2. Run rule-based RCA.
        3. Generate FixPlan from RCA result.
        4. Add FixPlan to final response.
        """
        diagnostics = self.kubernetes_client.collect_diagnostics(
            namespace=request.namespace,
            deployment_name=request.deployment_name,
            service_name=request.service_name,
        )

        rca_result = self.rca_engine.analyze(diagnostics)

        fix_plan = self.git_analyzer.analyze(rca_result)

        rca_result["fix_plan"] = fix_plan.to_dict()

        return rca_result