"""
Main orchestration service for the AI DevOps On-Call Agent.

Workflow:
1. Collect Kubernetes diagnostics.
2. Run rule-based RCA.
3. Generate FixPlan using GitAnalyzer.
4. Verify target file in GitHub repository.
5. Update manifest in memory when applicable.
6. Return final response.
"""

from app.clients.kubernetes_client import KubernetesClient
from app.services.rule_based_rca_engine import RuleBasedRcaEngine
from app.services.git_analyzer import GitAnalyzer
from app.services.repository_analysis_service import RepositoryAnalysisService
from app.services.manifest_updater import ManifestUpdater


class OnCallAgentService:
    """
    Coordinates incident analysis across Kubernetes, RCA, Git analysis,
    repository analysis, and manifest update planning.
    """

    def __init__(self):
        self.kubernetes_client = KubernetesClient()
        self.rca_engine = RuleBasedRcaEngine()
        self.git_analyzer = GitAnalyzer()
        self.repository_analysis_service = RepositoryAnalysisService()
        self.manifest_updater = ManifestUpdater()

    def analyze_incident(self, request):
        diagnostics = self.kubernetes_client.collect_diagnostics(
            namespace=request.namespace,
            deployment_name=request.deployment_name,
            service_name=request.service_name,
        )

        rca_result = self.rca_engine.analyze(diagnostics)

        fix_plan = self.git_analyzer.analyze(rca_result)
        fix_plan_dict = fix_plan.to_dict()

        repository_analysis = self.repository_analysis_service.analyze_fix_plan(
            fix_plan_dict
        )

        manifest_update = {
            "enabled": True,
            "status": "SKIPPED",
            "message": "Manifest update was not attempted."
        }

        if repository_analysis.get("status") == "TARGET_FILE_FOUND":
            manifest_update = self.manifest_updater.update_manifest(
                file_content=repository_analysis.get("content", ""),
                fix_plan=fix_plan_dict,
            )

        rca_result["fix_plan"] = fix_plan_dict
        rca_result["repository_analysis"] = repository_analysis
        rca_result["manifest_update"] = manifest_update

        return rca_result