from typing import Any, Dict, List, Optional

from app.models.detected_issue import DetectedIssue


class RcaResponseBuilder:
    """
    Builds final RCA API response from detected issues.

    This class does not detect issues.
    It only formats response.
    """

    def build_response(
        self,
        issues: List[DetectedIssue],
        diagnostics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build successful RCA response.
        """
        if not issues:
            issues = [self.healthy_issue()]

        primary_issue = issues[0]

        return {
            "summary": self._build_summary(primary_issue, diagnostics),
            "primary_issue": primary_issue.issue_type,
            "probable_root_cause": self._build_root_cause(primary_issue),
            "evidence": self._build_evidence(issues),
            "recommended_actions": self._build_recommended_actions(issues),
            "suggested_kubectl_commands": self._build_kubectl_commands(diagnostics),
            "confidence": self._calculate_confidence(primary_issue, issues),
            "diagnostics": diagnostics,
        }

    def build_unavailable_response(
        self,
        message: str,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build response when Kubernetes diagnostics cannot be collected.
        """
        diagnostics = diagnostics or {}

        namespace = diagnostics.get("namespace", "default")
        deployment = diagnostics.get("deployment_name", "<deployment-name>")

        return {
            "summary": "Unable to collect Kubernetes diagnostics.",
            "primary_issue": "DIAGNOSTICS_UNAVAILABLE",
            "probable_root_cause": "Kubernetes diagnostics collection failed.",
            "evidence": [message],
            "recommended_actions": [
                "Verify Kubernetes connectivity.",
                "Check namespace and deployment name.",
                "Check service account/RBAC permissions.",
            ],
            "suggested_kubectl_commands": [
                f"kubectl get pods -n {namespace}",
                f"kubectl describe deployment {deployment} -n {namespace}",
                f"kubectl get events -n {namespace} --sort-by=.lastTimestamp",
                f"kubectl logs -n {namespace} -l app={deployment} --tail=100",
            ],
            "confidence": 40,
            "diagnostics": diagnostics,
        }

    def healthy_issue(self) -> DetectedIssue:
        """
        Build healthy issue when no problem is detected.
        """
        return DetectedIssue(
            issue_type="HEALTHY",
            severity="LOW",
            score=20,
            evidence=[
                "Deployment replicas appear ready.",
                "Pods appear running and ready.",
                "No high-priority Kubernetes failure pattern detected.",
            ],
            actions=[
                "Continue monitoring deployment health.",
                "Check application-level metrics if user impact is still reported.",
            ],
        )

    def _build_summary(
        self,
        primary_issue: DetectedIssue,
        diagnostics: Dict[str, Any],
    ) -> str:
        """
        Build short human-readable RCA summary.
        """
        namespace = diagnostics.get("namespace", "unknown")
        deployment = diagnostics.get("deployment_name", "unknown")

        if primary_issue.issue_type == "HEALTHY":
            return f"Deployment '{deployment}' in namespace '{namespace}' appears healthy."

        return (
            f"Detected {primary_issue.issue_type} for deployment "
            f"'{deployment}' in namespace '{namespace}'."
        )

    def _build_root_cause(self, issue: DetectedIssue) -> str:
        """
        Convert issue type into human-readable root cause.
        """
        root_causes = {
            "CRASH_LOOP_BACKOFF": "Application container is repeatedly crashing after startup.",
            "IMAGE_PULL_BACKOFF": "Kubernetes is unable to pull the container image.",
            "OOM_KILLED": "Container is likely exceeding its memory limit.",
            "PROBE_FAILURE": "Kubernetes health probe is failing.",
            "SCHEDULING_FAILURE": "Pod cannot be scheduled on available nodes.",
            "NODE_FAILURE": "Underlying Kubernetes node may be unhealthy or unreachable.",
            "PVC_FAILURE": "Pod volume or persistent storage mount is failing.",
            "POD_NOT_RUNNING": "One or more pods are not running.",
            "POD_NOT_READY": "One or more pods are running but not ready.",
            "DEPLOYMENT_NOT_READY": "Deployment does not have desired ready replicas.",
            "HIGH_RESTART_COUNT": "Pod restart count is higher than expected.",
            "WARNING_EVENTS": "Kubernetes warning events were detected.",
            "ERROR_LOGS": "Application logs contain error indicators.",
            "HEALTHY": "No obvious Kubernetes issue detected.",
        }

        return root_causes.get(
            issue.issue_type,
            "Unable to determine root cause from available diagnostics.",
        )

    def _build_evidence(self, issues: List[DetectedIssue]) -> List[str]:
        """
        Build evidence list from detected issues.
        """
        evidence = []

        for issue in issues:
            evidence.append(
                f"{issue.issue_type} detected with severity={issue.severity}, score={issue.score}"
            )
            evidence.extend(issue.evidence)

        return self._deduplicate(evidence)

    def _build_recommended_actions(self, issues: List[DetectedIssue]) -> List[str]:
        """
        Build recommended action list from detected issues.
        """
        actions = []

        for issue in issues:
            actions.extend(issue.actions)

        return self._deduplicate(actions)

    def _build_kubectl_commands(self, diagnostics: Dict[str, Any]) -> List[str]:
        """
        Suggest useful kubectl commands for manual verification.
        """
        namespace = diagnostics.get("namespace", "default")
        deployment = diagnostics.get("deployment_name", "<deployment-name>")

        return [
            f"kubectl get deployment {deployment} -n {namespace}",
            f"kubectl describe deployment {deployment} -n {namespace}",
            f"kubectl get pods -n {namespace}",
            f"kubectl describe pods -n {namespace}",
            f"kubectl get events -n {namespace} --sort-by=.lastTimestamp",
            f"kubectl logs -n {namespace} -l app={deployment} --tail=100",
            f"kubectl logs -n {namespace} -l app={deployment} --previous --tail=100",
        ]

    def _calculate_confidence(
        self,
        primary_issue: DetectedIssue,
        all_issues: List[DetectedIssue],
    ) -> int:
        """
        Calculate confidence from primary issue and supporting signals.
        """
        if primary_issue.issue_type == "HEALTHY":
            return 85

        confidence = primary_issue.score

        if len(all_issues) >= 3:
            confidence += 5

        if primary_issue.severity == "CRITICAL":
            confidence += 3

        return min(confidence, 98)

    def _deduplicate(self, items: List[str]) -> List[str]:
        """
        Remove duplicate strings while keeping original order.
        """
        seen = set()
        result = []

        for item in items:
            if item not in seen:
                seen.add(item)
                result.append(item)

        return result