"""
Git Analyzer.

This service converts RCA output into a repository-aware FixPlan.

It does not modify files.
It does not create branches.
It does not create pull requests.

Its only job is:
RCA issue -> target file -> change type -> FixPlan
"""

from typing import Callable, Dict

from app.models.fix_plan import FixPlan


class GitAnalyzer:
    """
    Builds FixPlan objects from RCA results.
    """

    def __init__(self):
        """
        Register issue handlers.

        Each issue type maps to one method that knows how to build
        a FixPlan for that issue.
        """
        self.issue_handlers: Dict[str, Callable[[dict], FixPlan]] = {
            "IMAGE_PULL_BACKOFF": self._image_pull_fix,
            "PROBE_FAILURE": self._probe_fix,
            "OOM_KILLED": self._oom_fix,
            "CRASH_LOOP_BACKOFF": self._crash_loop_fix,
            "HIGH_RESTART_COUNT": self._restart_fix,
            "DEPLOYMENT_NOT_READY": self._deployment_not_ready_fix,
            "ERROR_LOGS": self._application_code_issue_fix,
        }

    def analyze(self, rca_result: dict) -> FixPlan:
        """
        Main entry point.

        Reads primary_issue from RCA result and returns a FixPlan.
        If issue type is unknown, returns manual review plan.
        """
        issue_type = rca_result.get("primary_issue")

        if not issue_type:
            issue_type = self._infer_issue_type(rca_result)

        handler = self.issue_handlers.get(issue_type)

        if not handler:
            return self._manual_fix(rca_result)

        return handler(rca_result)
    def _application_code_issue_fix(self, rca_result: dict) -> FixPlan:
        """
        Build FixPlan for application-level log errors.

        Application code issues must not be auto-fixed by this agent.
        """
        return FixPlan(
            issue_type="APPLICATION_CODE_ISSUE",
            can_auto_fix=False,
            target_file=None,
            change_type="APPLICATION_TEAM_REVIEW",
            reason="Application logs indicate an application-level issue. Auto-fix is disabled because this agent only changes Kubernetes manifests.",
            confidence=65,
            evidence=self._extract_evidence(rca_result),
            recommended_changes={
                "action": "Route to application team for code, dependency, configuration, or runtime investigation.",
            },
        )

    def _infer_issue_type(self, rca_result: dict) -> str:
        """
        Temporary fallback.

        If RCA response does not yet contain primary_issue,
        infer issue type from probable_root_cause text.
        Later we should rely only on primary_issue.
        """
        probable_root_cause = rca_result.get("probable_root_cause", "").lower()

        if "container image" in probable_root_cause:
            return "IMAGE_PULL_BACKOFF"

        if "probe" in probable_root_cause:
            return "PROBE_FAILURE"

        if "memory" in probable_root_cause:
            return "OOM_KILLED"

        if "crashing" in probable_root_cause:
            return "CRASH_LOOP_BACKOFF"

        if "restart" in probable_root_cause:
            return "HIGH_RESTART_COUNT"

        if "ready replicas" in probable_root_cause:
            return "DEPLOYMENT_NOT_READY"

        return "UNKNOWN"

    def _image_pull_fix(self, rca_result: dict) -> FixPlan:
        """
        Build FixPlan for ImagePullBackOff.

        Typical fix:
        - Verify image tag.
        - Update deployment manifest image field.
        """
        return FixPlan(
            issue_type="IMAGE_PULL_BACKOFF",
            can_auto_fix=True,
            target_file="k8s/base/backend-deployment.yaml",
            change_type="UPDATE_IMAGE_TAG",
            reason="Deployment is using an invalid or unavailable container image tag.",
            confidence=95,
            evidence=self._extract_evidence(rca_result),
            recommended_changes={
                "field": "containers[].image",
                "action": "Replace invalid image tag with a valid image tag.",
            },
        )

    def _probe_fix(self, rca_result: dict) -> FixPlan:
        """
        Build FixPlan for readiness/liveness probe failure.

        Typical fix:
        - Correct probe path.
        - Correct probe port.
        - Increase initial delay or timeout.
        """
        return FixPlan(
            issue_type="PROBE_FAILURE",
            can_auto_fix=True,
            target_file="k8s/base/backend-deployment.yaml",
            change_type="UPDATE_PROBE",
            reason="Kubernetes health probe appears to be failing.",
            confidence=90,
            evidence=self._extract_evidence(rca_result),
            recommended_changes={
                "field": "readinessProbe/livenessProbe",
                "action": "Review probe path, port, timeout, and initial delay.",
            },
        )

    def _oom_fix(self, rca_result: dict) -> FixPlan:
        """
        Build FixPlan for OOMKilled.

        Typical fix:
        - Increase memory limit.
        - Review application memory usage.
        """
        return FixPlan(
            issue_type="OOM_KILLED",
            can_auto_fix=True,
            target_file="k8s/base/backend-deployment.yaml",
            change_type="UPDATE_MEMORY_LIMIT",
            reason="Container appears to be exceeding its configured memory limit.",
            confidence=88,
            evidence=self._extract_evidence(rca_result),
            recommended_changes={
                "field": "resources.limits.memory",
                "action": "Increase memory limit after validating usage pattern.",
            },
        )

    def _crash_loop_fix(self, rca_result: dict) -> FixPlan:
        """
        Build FixPlan for CrashLoopBackOff.

        This may require code or configuration analysis,
        so auto-fix is disabled for now.
        """
        return FixPlan(
            issue_type="CRASH_LOOP_BACKOFF",
            can_auto_fix=False,
            target_file=None,
            change_type="CODE_OR_CONFIG_ANALYSIS_REQUIRED",
            reason="Container is repeatedly crashing; code or configuration analysis is required.",
            confidence=80,
            evidence=self._extract_evidence(rca_result),
            recommended_changes={
                "action": "Analyze application logs, config maps, secrets, and recent commits.",
            },
        )

    def _restart_fix(self, rca_result: dict) -> FixPlan:
        """
        Build FixPlan for high restart count.

        This is a symptom, so manual/AI analysis is safer.
        """
        return FixPlan(
            issue_type="HIGH_RESTART_COUNT",
            can_auto_fix=False,
            target_file=None,
            change_type="RUNTIME_ANALYSIS_REQUIRED",
            reason="Pod restart count is high; root cause needs deeper runtime analysis.",
            confidence=70,
            evidence=self._extract_evidence(rca_result),
            recommended_changes={
                "action": "Check previous logs, resource limits, probes, and dependency failures.",
            },
        )

    def _deployment_not_ready_fix(self, rca_result: dict) -> FixPlan:
        """
        Build FixPlan for deployment not ready.

        This is usually caused by another lower-level issue,
        so direct auto-fix is disabled.
        """
        return FixPlan(
            issue_type="DEPLOYMENT_NOT_READY",
            can_auto_fix=False,
            target_file=None,
            change_type="CHECK_POD_LEVEL_CAUSE",
            reason="Deployment is not ready; pod-level cause should be inspected first.",
            confidence=70,
            evidence=self._extract_evidence(rca_result),
            recommended_changes={
                "action": "Check pods, events, image, probes, scheduling, and logs.",
            },
        )

    def _manual_fix(self, rca_result: dict) -> FixPlan:
        """
        Build fallback FixPlan for unknown or unsupported issues.
        """
        return FixPlan(
            issue_type=rca_result.get("primary_issue", "UNKNOWN"),
            can_auto_fix=False,
            target_file=None,
            change_type="MANUAL_REVIEW",
            reason=rca_result.get(
                "probable_root_cause",
                "Issue is not supported by GitAnalyzer yet.",
            ),
            confidence=50,
            evidence=self._extract_evidence(rca_result),
            recommended_changes={
                "action": "Manual review or AI analysis required.",
            },
        )

    def _extract_evidence(self, rca_result: dict) -> list[str]:
        """
        Extract limited evidence from RCA result for FixPlan.

        We keep it short so PR descriptions do not become noisy.
        """
        evidence = rca_result.get("evidence") or []
        return evidence[:5]