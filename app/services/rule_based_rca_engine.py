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
            return self._build_kubernetes_unavailable_response(diagnostics)

        issues = self.issue_detector.detect(diagnostics)
        issues = self._filter_stale_issues(issues, diagnostics)
        issues = self._prioritize_issues(issues)

        return self.response_builder.build_response(
            issues=issues,
            diagnostics=diagnostics,
        )

    def _build_kubernetes_unavailable_response(
        self,
        diagnostics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build clear RCA response when Kubernetes diagnostics cannot be collected.
        """
        error = diagnostics.get("error", "Kubernetes diagnostics unavailable.")
        error_type = diagnostics.get("error_type", "DIAGNOSTICS_UNAVAILABLE")
        namespace = diagnostics.get("namespace", "default")
        deployment_name = diagnostics.get("deployment_name", "<deployment-name>")

        if error_type == "KUBERNETES_API_DNS_FAILURE":
            return {
                "summary": "Unable to connect to Kubernetes API server due to DNS resolution failure.",
                "primary_issue": "KUBERNETES_API_DNS_FAILURE",
                "probable_root_cause": "Analyzer could not resolve the Kubernetes API server DNS name.",
                "evidence": [error],
                "recommended_actions": [
                    "Verify AKS cluster is running.",
                    "Run az aks get-credentials again.",
                    "Check current kubectl context.",
                    "Verify DNS/network/VPN access from analyzer runtime.",
                ],
                "suggested_kubectl_commands": [
                    "kubectl config current-context",
                    "kubectl cluster-info",
                    f"kubectl get deployment {deployment_name} -n {namespace}",
                    f"kubectl get events -n {namespace} --sort-by=.lastTimestamp",
                ],
                "confidence": 70,
                "diagnostics": diagnostics,
            }

        if error_type == "KUBERNETES_RBAC_FORBIDDEN":
            return {
                "summary": "Kubernetes diagnostics failed because access was forbidden.",
                "primary_issue": "KUBERNETES_RBAC_FORBIDDEN",
                "probable_root_cause": "Analyzer does not have sufficient RBAC permissions to read Kubernetes resources.",
                "evidence": [error],
                "recommended_actions": [
                    "Verify service account permissions.",
                    "Check Role or ClusterRole bindings.",
                    "Ensure analyzer can read deployments, pods, events, and logs.",
                ],
                "suggested_kubectl_commands": [
                    f"kubectl auth can-i get deployments -n {namespace}",
                    f"kubectl auth can-i get pods -n {namespace}",
                    f"kubectl auth can-i get events -n {namespace}",
                    f"kubectl auth can-i get pods/log -n {namespace}",
                ],
                "confidence": 75,
                "diagnostics": diagnostics,
            }

        if error_type == "DEPLOYMENT_NOT_FOUND":
            return {
                "summary": "Deployment was not found in the target namespace.",
                "primary_issue": "DEPLOYMENT_NOT_FOUND",
                "probable_root_cause": "The deployment name or namespace may be incorrect, or the deployment may not exist.",
                "evidence": [error],
                "recommended_actions": [
                    "Verify deployment name.",
                    "Verify namespace.",
                    "Check whether the deployment was deleted or not yet created.",
                ],
                "suggested_kubectl_commands": [
                    f"kubectl get deployment {deployment_name} -n {namespace}",
                    f"kubectl get deployments -n {namespace}",
                    "kubectl get namespaces",
                ],
                "confidence": 80,
                "diagnostics": diagnostics,
            }

        if error_type in {
            "KUBERNETES_API_UNAVAILABLE",
            "KUBERNETES_API_TIMEOUT",
            "KUBERNETES_API_CONNECTION_REFUSED",
        }:
            return {
                "summary": "Unable to connect to Kubernetes API server.",
                "primary_issue": error_type,
                "probable_root_cause": "Kubernetes API server is unavailable or unreachable from the analyzer runtime.",
                "evidence": [error],
                "recommended_actions": [
                    "Verify cluster is running.",
                    "Check kubeconfig and current context.",
                    "Verify network/VPN/firewall access.",
                    "Retry after Kubernetes API connectivity is restored.",
                ],
                "suggested_kubectl_commands": [
                    "kubectl config current-context",
                    "kubectl cluster-info",
                    f"kubectl get deployment {deployment_name} -n {namespace}",
                    f"kubectl get pods -n {namespace}",
                ],
                "confidence": 70,
                "diagnostics": diagnostics,
            }

        return self.response_builder.build_unavailable_response(
            error,
            diagnostics,
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

    """
        Prioritize detected issues based on confidence score.
        Note: Score shows detection confidence, not always the actual root cause.
    """
    def _prioritize_issues(self, issues: List[DetectedIssue]) -> List[DetectedIssue]:
        """
        Sort issues by score, highest first.
        """
        return sorted(issues, key=lambda issue: issue.score, reverse=True)