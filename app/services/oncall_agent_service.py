"""
Main orchestration service for the AI DevOps On-Call Agent.
"""

from app.clients.kubernetes_client import KubernetesClient
from app.services.rule_based_rca_engine import RuleBasedRcaEngine
from app.services.git_analyzer import GitAnalyzer
from app.services.repository_analysis_service import RepositoryAnalysisService
from app.services.manifest_updater import ManifestUpdater
from app.services.pull_request_service import PullRequestService
from app.services.ai_fix_plan_service import AiFixPlanService
from app.services.ai_fix_plan_reviewer_service import AiFixPlanReviewerService


class OnCallAgentService:
    """
    Coordinates the complete AI DevOps On-Call workflow.

    Flow:
    Kubernetes Diagnostics
        -> Rule-Based RCA
        -> Rule-Based FixPlan
        -> AI FixPlan Fallback if needed
        -> Repository Analysis
        -> Manifest Update
        -> AI Review
        -> Pull Request Decision
        -> Final API Response
    """

    def __init__(self):
        self.kubernetes_client = KubernetesClient()
        self.rca_engine = RuleBasedRcaEngine()
        self.git_analyzer = GitAnalyzer()
        self.repository_analysis_service = RepositoryAnalysisService()
        self.manifest_updater = ManifestUpdater()
        self.pull_request_service = PullRequestService()
        self.ai_fix_plan_service = AiFixPlanService()
        self.ai_fix_plan_reviewer_service = AiFixPlanReviewerService()

    def analyze_incident(self, request):
        diagnostics = self.kubernetes_client.collect_diagnostics(
            namespace=request.namespace,
            deployment_name=request.deployment_name,
            service_name=request.service_name,
        )

        rca_result = self.rca_engine.analyze(diagnostics)

        rule_fix_plan = self.git_analyzer.analyze(rca_result)
        rule_fix_plan_dict = rule_fix_plan.to_dict()

        final_fix_plan = rule_fix_plan_dict
        ai_fix_plan = None

        if self._should_use_ai_fallback(rule_fix_plan_dict):
            ai_fix_plan = self.ai_fix_plan_service.generate_fix_plan(
                request=request,
                diagnostics=diagnostics,
                rca_result=rca_result,
                rule_based_fix_plan=rule_fix_plan_dict,
            )

            if ai_fix_plan and ai_fix_plan.get("can_auto_fix") is True:
                final_fix_plan = ai_fix_plan

        repository_analysis = self.repository_analysis_service.analyze_fix_plan(
            final_fix_plan
        )

        manifest_update = {
            "enabled": True,
            "status": "SKIPPED",
            "message": "Manifest update was not attempted.",
        }

        if repository_analysis.get("status") == "TARGET_FILE_FOUND":
            manifest_update = self.manifest_updater.update_manifest(
                file_content=repository_analysis.get("content", ""),
                fix_plan=final_fix_plan,
            )

        ai_review = self.ai_fix_plan_reviewer_service.review_fix_plan(
            request=request,
            diagnostics=diagnostics,
            rca_result=rca_result,
            fix_plan=final_fix_plan,
            repository_analysis=repository_analysis,
            manifest_update=manifest_update,
        )

        pull_request = self.pull_request_service.create_fix_pr(
            fix_plan=final_fix_plan,
            repository_analysis=repository_analysis,
            manifest_update=manifest_update,
            deployment_name=request.deployment_name,
            ai_review=ai_review,
        )

        rca_result["rule_fix_plan"] = rule_fix_plan_dict
        rca_result["ai_fix_plan"] = ai_fix_plan
        rca_result["fix_plan"] = final_fix_plan
        rca_result["repository_analysis"] = repository_analysis
        rca_result["manifest_update"] = manifest_update
        rca_result["ai_review"] = ai_review
        rca_result["pull_request"] = pull_request

        return rca_result

    def _should_use_ai_fallback(self, fix_plan_dict):
        issue_type = fix_plan_dict.get("issue_type")
        confidence = fix_plan_dict.get("confidence", 0)

        if issue_type == "HEALTHY":
            return False

        return (
            not fix_plan_dict.get("can_auto_fix")
            or issue_type in [None, "UNKNOWN"]
            or confidence < 70
        )
