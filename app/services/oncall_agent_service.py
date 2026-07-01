"""
Main orchestration service for the AI DevOps On-Call Agent.

Workflow:
1. Collect Kubernetes diagnostics.
2. Run rule-based RCA.
3. Generate FixPlan using GitAnalyzer.
4. Verify target file in GitHub repository.
5. Update manifest in memory when applicable.
6. Decide whether a Pull Request should be created.
7. Return final response.
"""

from app.clients.kubernetes_client import KubernetesClient
from app.services.rule_based_rca_engine import RuleBasedRcaEngine
from app.services.git_analyzer import GitAnalyzer
from app.services.repository_analysis_service import RepositoryAnalysisService
from app.services.manifest_updater import ManifestUpdater
from app.services.pull_request_service import PullRequestService


class OnCallAgentService:
    """
    Coordinates the complete AI DevOps On-Call workflow.

    Workflow:
    Kubernetes Diagnostics
            ↓
    Rule-Based RCA
            ↓
    FixPlan Generation
            ↓
    Repository Analysis
            ↓
    Manifest Update (In Memory)
            ↓
    Pull Request Decision
            ↓
    Final API Response
    """

    def __init__(self):
        """Initialize all service dependencies."""
        self.kubernetes_client = KubernetesClient()
        self.rca_engine = RuleBasedRcaEngine()
        self.git_analyzer = GitAnalyzer()
        self.repository_analysis_service = RepositoryAnalysisService()
        self.manifest_updater = ManifestUpdater()
        self.pull_request_service = PullRequestService()

    def analyze_incident(self, request):
        """
        Analyze an incident and generate the complete response.
        """

        # ---------------------------------------------------------
        # Step 1 - Kubernetes Diagnostics
        # ---------------------------------------------------------
        diagnostics = self.kubernetes_client.collect_diagnostics(
            namespace=request.namespace,
            deployment_name=request.deployment_name,
            service_name=request.service_name,
        )

        # ---------------------------------------------------------
        # Step 2 - Rule-Based RCA
        # ---------------------------------------------------------
        rca_result = self.rca_engine.analyze(diagnostics)

        # ---------------------------------------------------------
        # Step 3 - Generate FixPlan
        # ---------------------------------------------------------
        fix_plan = self.git_analyzer.analyze(rca_result)
        fix_plan_dict = fix_plan.to_dict()

        # ---------------------------------------------------------
        # Step 4 - Repository Analysis
        # ---------------------------------------------------------
        repository_analysis = (
            self.repository_analysis_service.analyze_fix_plan(
                fix_plan_dict
            )
        )

        # ---------------------------------------------------------
        # Step 5 - Manifest Update (In Memory Only)
        # ---------------------------------------------------------
        manifest_update = {
            "enabled": True,
            "status": "SKIPPED",
            "message": "Manifest update was not attempted.",
        }

        if repository_analysis.get("status") == "TARGET_FILE_FOUND":
            manifest_update = self.manifest_updater.update_manifest(
                file_content=repository_analysis.get("content", ""),
                fix_plan=fix_plan_dict,
            )

        # ---------------------------------------------------------
        # Step 6 - Pull Request Decision
        # ---------------------------------------------------------
        pull_request = self.pull_request_service.create_fix_pr(
            fix_plan=fix_plan_dict,
            repository_analysis=repository_analysis,
            manifest_update=manifest_update,
            deployment_name=request.deployment_name,
        )

        # ---------------------------------------------------------
        # Step 7 - Build Final Response
        # ---------------------------------------------------------
        rca_result["fix_plan"] = fix_plan_dict
        rca_result["repository_analysis"] = repository_analysis
        rca_result["manifest_update"] = manifest_update
        rca_result["pull_request"] = pull_request

        return rca_result