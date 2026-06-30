from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DetectedIssue:
    issue_type: str
    severity: str
    score: int
    evidence: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)


class RuleBasedRcaEngine:
    """
    Rule-based Kubernetes RCA engine.

    This engine does not call OpenAI.
    It detects known Kubernetes failure patterns and returns
    prioritized root-cause candidates.
    """

    def analyze(self, diagnostics: Dict[str, Any]) -> Dict[str, Any]:
        if not diagnostics:
            return self._build_unavailable_response("No diagnostics received.")

        if diagnostics.get("error"):
            return self._build_unavailable_response(
                diagnostics.get("error"),
                diagnostics,
            )

        issues = self._detect_issues(diagnostics)
        issues = self._filter_stale_issues(issues, diagnostics)
        issues = self._prioritize_issues(issues)

        if not issues:
            issues = [self._healthy_issue()]

        primary_issue = issues[0]

        return {
            "summary": self._build_summary(primary_issue, diagnostics),
            "probable_root_cause": self._build_root_cause(primary_issue),
            "evidence": self._build_evidence(issues),
            "recommended_actions": self._build_recommended_actions(issues),
            "suggested_kubectl_commands": self._build_kubectl_commands(diagnostics),
            "confidence": self._calculate_confidence(primary_issue, issues),
            "diagnostics": diagnostics,
        }

    def _detect_issues(self, diagnostics: Dict[str, Any]) -> List[DetectedIssue]:
        issues: List[DetectedIssue] = []

        issues.extend(self._check_deployment_health(diagnostics))
        issues.extend(self._check_pod_health(diagnostics))
        issues.extend(self._check_restart_count(diagnostics))
        issues.extend(self._check_crash_loop_backoff(diagnostics))
        issues.extend(self._check_image_pull_backoff(diagnostics))
        issues.extend(self._check_oom_killed(diagnostics))
        issues.extend(self._check_probe_failures(diagnostics))
        issues.extend(self._check_scheduling_failures(diagnostics))
        issues.extend(self._check_node_failures(diagnostics))
        issues.extend(self._check_pvc_failures(diagnostics))
        issues.extend(self._check_warning_events(diagnostics))
        issues.extend(self._check_error_logs(diagnostics))

        return issues

    def _check_deployment_health(self, diagnostics: Dict[str, Any]) -> List[DetectedIssue]:
        status = diagnostics.get("deployment_status") or {}

        replicas = status.get("replicas") or 0
        ready = status.get("ready_replicas") or 0
        available = status.get("available_replicas") or 0
        updated = status.get("updated_replicas") or 0

        if replicas > 0 and ready < replicas:
            return [
                DetectedIssue(
                    issue_type="DEPLOYMENT_NOT_READY",
                    severity="HIGH",
                    score=70,
                    evidence=[
                        f"Deployment replicas: desired={replicas}, ready={ready}, available={available}, updated={updated}"
                    ],
                    actions=[
                        "Describe the deployment and check rollout status.",
                        "Check pod readiness, events, image, probes, and scheduling issues.",
                    ],
                )
            ]

        return []
    
    def _check_pod_health(self, diagnostics: Dict[str, Any]) -> List[DetectedIssue]:
        issues = []
        pods = diagnostics.get("pods") or []

        for pod in pods:
            name = pod.get("name", "unknown-pod")
            phase = pod.get("phase")
            ready = pod.get("ready")

            if phase != "Running":
                issues.append(
                    DetectedIssue(
                        issue_type="POD_NOT_RUNNING",
                        severity="HIGH",
                        score=75,
                        evidence=[f"Pod {name} is in phase {phase}."],
                        actions=[
                            f"Run kubectl describe pod {name}.",
                            "Check scheduling, image pull, PVC, and node-related events.",
                        ],
                    )
                )

            if phase == "Running" and ready is False:
                issues.append(
                    DetectedIssue(
                        issue_type="POD_NOT_READY",
                        severity="MEDIUM",
                        score=60,
                        evidence=[f"Pod {name} is running but not ready."],
                        actions=[
                            f"Check readiness probe and application health for pod {name}.",
                            f"Inspect logs for pod {name}.",
                        ],
                    )
                )

        return issues

    def _check_restart_count(self, diagnostics: Dict[str, Any]) -> List[DetectedIssue]:
        issues = []
        pods = diagnostics.get("pods") or []

        for pod in pods:
            name = pod.get("name", "unknown-pod")
            restart_count = pod.get("restart_count") or 0

            if restart_count >= 5:
                issues.append(
                    DetectedIssue(
                        issue_type="HIGH_RESTART_COUNT",
                        severity="HIGH",
                        score=80,
                        evidence=[f"Pod {name} has restarted {restart_count} times."],
                        actions=[
                            f"Check previous logs using kubectl logs {name} --previous.",
                            "Check for application crash, OOMKilled, failed probes, or dependency failures.",
                        ],
                    )
                )
            elif restart_count >= 2:
                issues.append(
                    DetectedIssue(
                        issue_type="HIGH_RESTART_COUNT",
                        severity="MEDIUM",
                        score=55,
                        evidence=[f"Pod {name} has restarted {restart_count} times."],
                        actions=[
                            f"Review logs for pod {name}.",
                            "Monitor if restart count continues increasing.",
                        ],
                    )
                )

        return issues

    def _check_crash_loop_backoff(self, diagnostics: Dict[str, Any]) -> List[DetectedIssue]:
        return self._detect_from_events(
            diagnostics,
            issue_type="CRASH_LOOP_BACKOFF",
            severity="CRITICAL",
            score=95,
            keywords=["CrashLoopBackOff", "Back-off restarting failed container"],
            actions=[
                "Check application startup logs.",
                "Run kubectl logs <pod-name> --previous.",
                "Verify environment variables, secrets, config maps, and application dependencies.",
            ],
        )

    def _check_image_pull_backoff(self, diagnostics: Dict[str, Any]) -> List[DetectedIssue]:
        return self._detect_from_events(
            diagnostics,
            issue_type="IMAGE_PULL_BACKOFF",
            severity="CRITICAL",
            score=95,
            keywords=["ImagePullBackOff", "ErrImagePull", "Failed to pull image"],
            actions=[
                "Verify image name and tag.",
                "Check ACR/Docker registry authentication.",
                "Verify imagePullSecrets and repository permissions.",
            ],
        )

    def _check_oom_killed(self, diagnostics: Dict[str, Any]) -> List[DetectedIssue]:
        issues = self._detect_from_events(
            diagnostics,
            issue_type="OOM_KILLED",
            severity="CRITICAL",
            score=90,
            keywords=["OOMKilled", "memory limit", "out of memory"],
            actions=[
                "Check container memory limit and actual memory usage.",
                "Increase memory limit if needed.",
                "Investigate memory leaks or high heap usage.",
            ],
        )

        logs_text = self._logs_as_text(diagnostics).lower()
        if "outofmemoryerror" in logs_text or "java heap space" in logs_text:
            issues.append(
                DetectedIssue(
                    issue_type="OOM_KILLED",
                    severity="CRITICAL",
                    score=90,
                    evidence=["Application logs contain Java memory error keywords."],
                    actions=[
                        "Review JVM heap settings.",
                        "Increase container memory limit.",
                        "Analyze heap usage and possible memory leak.",
                    ],
                )
            )

        return issues

    def _check_probe_failures(self, diagnostics: Dict[str, Any]) -> List[DetectedIssue]:
        return self._detect_from_events(
            diagnostics,
            issue_type="PROBE_FAILURE",
            severity="HIGH",
            score=85,
            keywords=[
                "Readiness probe failed",
                "Liveness probe failed",
                "Startup probe failed",
                "probe failed",
            ],
            actions=[
                "Verify readiness/liveness probe path and port.",
                "Check application startup time.",
                "Increase initialDelaySeconds or timeoutSeconds if startup is slow.",
            ],
        )

    def _check_scheduling_failures(self, diagnostics: Dict[str, Any]) -> List[DetectedIssue]:
        return self._detect_from_events(
            diagnostics,
            issue_type="SCHEDULING_FAILURE",
            severity="HIGH",
            score=88,
            keywords=[
                "FailedScheduling",
                "Insufficient cpu",
                "Insufficient memory",
                "node(s) had taint",
                "didn't match Pod's node affinity",
            ],
            actions=[
                "Check node capacity and pod resource requests.",
                "Check taints, tolerations, node selectors, and affinity rules.",
                "Scale node pool if cluster capacity is insufficient.",
            ],
        )

    def _check_node_failures(self, diagnostics: Dict[str, Any]) -> List[DetectedIssue]:
        return self._detect_from_events(
            diagnostics,
            issue_type="NODE_FAILURE",
            severity="HIGH",
            score=82,
            keywords=[
                "NodeNotReady",
                "node is not ready",
                "node.kubernetes.io/not-ready",
                "unreachable",
            ],
            actions=[
                "Check node status using kubectl get nodes.",
                "Describe the affected node.",
                "Check AKS node pool health.",
            ],
        )

    def _check_pvc_failures(self, diagnostics: Dict[str, Any]) -> List[DetectedIssue]:
        return self._detect_from_events(
            diagnostics,
            issue_type="PVC_FAILURE",
            severity="HIGH",
            score=86,
            keywords=[
                "persistentvolumeclaim",
                "PVC",
                "volume",
                "FailedMount",
                "Unable to attach or mount volumes",
            ],
            actions=[
                "Check PVC status.",
                "Check storage class and volume binding.",
                "Describe pod and PVC for mount errors.",
            ],
        )

    def _check_warning_events(self, diagnostics: Dict[str, Any]) -> List[DetectedIssue]:
        issues = []
        events = diagnostics.get("events") or []

        warning_events = [
            event for event in events
            if str(event.get("type", "")).lower() == "warning"
        ]

        if warning_events:
            evidence = []
            for event in warning_events[:5]:
                reason = event.get("reason", "Unknown")
                message = event.get("message", "")
                evidence.append(f"Warning event: {reason} - {message}")

            issues.append(
                DetectedIssue(
                    issue_type="WARNING_EVENTS",
                    severity="MEDIUM",
                    score=50,
                    evidence=evidence,
                    actions=[
                        "Review Kubernetes warning events.",
                        "Correlate events with pod status and logs.",
                    ],
                )
            )

        return issues

    def _check_error_logs(self, diagnostics: Dict[str, Any]) -> List[DetectedIssue]:
        logs_text = self._logs_as_text(diagnostics)

        error_keywords = [
            "exception",
            "error",
            "failed",
            "timeout",
            "connection refused",
            "unable to connect",
            "permission denied",
        ]

        matched = [
            keyword for keyword in error_keywords
            if keyword in logs_text.lower()
        ]

        if matched:
            return [
                DetectedIssue(
                    issue_type="ERROR_LOGS",
                    severity="MEDIUM",
                    score=65,
                    evidence=[f"Application logs contain error keywords: {', '.join(matched)}"],
                    actions=[
                        "Inspect application logs around the error timestamp.",
                        "Check dependent services such as database, config, secrets, and network connectivity.",
                    ],
                )
            ]

        return []

    def _detect_from_events(
        self,
        diagnostics: Dict[str, Any],
        issue_type: str,
        severity: str,
        score: int,
        keywords: List[str],
        actions: List[str],
    ) -> List[DetectedIssue]:
        events = diagnostics.get("events") or []
        matched_evidence = []

        for event in events:
            reason = str(event.get("reason", ""))
            message = str(event.get("message", ""))
            combined = f"{reason} {message}"

            if any(keyword.lower() in combined.lower() for keyword in keywords):
                matched_evidence.append(f"{reason} - {message}")

        if not matched_evidence:
            return []

        return [
            DetectedIssue(
                issue_type=issue_type,
                severity=severity,
                score=score,
                evidence=matched_evidence[:5],
                actions=actions,
            )
        ]

    def _prioritize_issues(self, issues: List[DetectedIssue]) -> List[DetectedIssue]:
        return sorted(issues, key=lambda issue: issue.score, reverse=True)

    def _build_summary(
        self,
        primary_issue: DetectedIssue,
        diagnostics: Dict[str, Any],
    ) -> str:
        namespace = diagnostics.get("namespace", "unknown")
        deployment = diagnostics.get("deployment_name", "unknown")

        if primary_issue.issue_type == "HEALTHY":
            return f"Deployment '{deployment}' in namespace '{namespace}' appears healthy."

        return (
            f"Detected {primary_issue.issue_type} for deployment "
            f"'{deployment}' in namespace '{namespace}'."
        )

    def _build_root_cause(self, issue: DetectedIssue) -> str:
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

        return root_causes.get(issue.issue_type, "Unable to determine root cause from available diagnostics.")

    def _build_evidence(self, issues: List[DetectedIssue]) -> List[str]:
        evidence = []

        for issue in issues:
            evidence.append(
                f"{issue.issue_type} detected with severity={issue.severity}, score={issue.score}"
            )
            evidence.extend(issue.evidence)

        return self._deduplicate(evidence)

    def _build_recommended_actions(self, issues: List[DetectedIssue]) -> List[str]:
        actions = []

        for issue in issues:
            actions.extend(issue.actions)

        return self._deduplicate(actions)

    def _build_kubectl_commands(self, diagnostics: Dict[str, Any]) -> List[str]:
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
        if primary_issue.issue_type == "HEALTHY":
            return 85

        confidence = primary_issue.score

        if len(all_issues) >= 3:
            confidence += 5

        if primary_issue.severity == "CRITICAL":
            confidence += 3

        return min(confidence, 98)

    def _healthy_issue(self) -> DetectedIssue:
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

    def _build_unavailable_response(
        self,
        message: str,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        diagnostics = diagnostics or {}

        namespace = diagnostics.get("namespace", "default")
        deployment = diagnostics.get("deployment_name", "<deployment-name>")

        return {
            "summary": "Unable to collect Kubernetes diagnostics.",
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

    def _logs_as_text(self, diagnostics: Dict[str, Any]) -> str:
        logs = diagnostics.get("logs") or ""

        if isinstance(logs, str):
            return logs

        if isinstance(logs, list):
            return "\n".join(str(item) for item in logs)

        if isinstance(logs, dict):
            return "\n".join(str(value) for value in logs.values())

        return str(logs)

    def _deduplicate(self, items: List[str]) -> List[str]:
        seen = set()
        result = []

        for item in items:
            if item not in seen:
                seen.add(item)
                result.append(item)

        return result
    def _filter_stale_issues(
        self,
        issues: List[DetectedIssue],
        diagnostics: Dict[str, Any],
    ) -> List[DetectedIssue]:
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