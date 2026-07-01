from typing import Any, Dict, List

from app.models.detected_issue import DetectedIssue
from app.services.kubernetes_issue_detector import KubernetesIssueDetector
from app.services.rca_response_builder import RcaResponseBuilder


class RuleBasedRcaEngine:
    """
    Orchestrates rule-based RCA.

    This class coordinates:
    1. Issue detection
    2. Stale issue filtering
    3. Issue prioritization
    4. Response building
    """

    def __init__(self):
        """
        Initialize detector and response builder.
        """
        self.issue_detector = KubernetesIssueDetector()
        self.response_builder = RcaResponseBuilder()

    def analyze(self, diagnostics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main RCA entry point.
        """
        if not diagnostics:
            return self.response_builder.build_unavailable_response(
                "No diagnostics received."
            )

        if diagnostics.get("error"):
            return self.response_builder.build_unavailable_response(
                diagnostics.get("error"),
                diagnostics,
            )

        issues = self.issue_detector.detect(diagnostics)
        issues = self._filter_stale_issues(issues, diagnostics)
        issues = self._prioritize_issues(issues)

        return self.response_builder.build_response(
            issues=issues,
            diagnostics=diagnostics,
        )

    def _filter_stale_issues(
        self,
        issues: List[DetectedIssue],
        diagnostics: Dict[str, Any],
    ) -> List[DetectedIssue]:
        """
        Remove stale event-based issues if current deployment and pods are healthy.
        """
        deployment_status = diagnostics.get("deployment_status") or {}
        pods = diagnostics.get("pods") or []

        replicas = deployment_status.get("replicas") or 0
        ready_replicas = deployment_status.get("ready_replicas") or 0

        deployment_healthy = replicas > 0 and replicas == ready_replicas

        pods_healthy = bool(pods) and all(
            pod.get("phase") == "Running" and pod.get("ready") is True
            for pod in pods
        )

        if not deployment_healthy or not pods_healthy:
            return issues

        stale_issue_types = {
            "IMAGE_PULL_BACKOFF",
            "CRASH_LOOP_BACKOFF",
            "OOM_KILLED",
            "PROBE_FAILURE",
            "SCHEDULING_FAILURE",
            "NODE_FAILURE",
            "PVC_FAILURE",
            "WARNING_EVENTS",
        }

        return [
            issue
            for issue in issues
            if issue.issue_type not in stale_issue_types
        ]

    def _prioritize_issues(self, issues: List[DetectedIssue]) -> List[DetectedIssue]:
        """
        Sort issues by score, highest first.
        """
        return sorted(issues, key=lambda issue: issue.score, reverse=True)