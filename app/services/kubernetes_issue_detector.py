from typing import Any, Dict, List

from app.models.detected_issue import DetectedIssue


class KubernetesIssueDetector:
    """
    Detects Kubernetes issues from diagnostics.

    This class only detects problems.
    It does not build final API response.
    """

    def detect(self, diagnostics: Dict[str, Any]) -> List[DetectedIssue]:
        """
        Run all issue checks and return detected issues.
        """
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
        """
        Detect deployment replica mismatch.
        """
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
        """
        Detect pods that are not running or not ready.
        """
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
        """
        Detect pods with high restart count.
        """
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
        """
        Detect CrashLoopBackOff from Kubernetes events.
        """
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
        """
        Detect image pull failures from Kubernetes events.
        """
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
        """
        Detect OOMKilled from events and application logs.
        """
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

        logs_text = self._application_logs_as_text(diagnostics).lower()

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
        """
        Detect readiness/liveness/startup probe failures.
        """
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
        """
        Detect pod scheduling failures.
        """
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
        """
        Detect node failure related events.
        """
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
        """
        Detect PVC or volume mount failures.
        """
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
        """
        Capture generic Kubernetes warning events.
        """
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
        """
        Detect application-level error keywords from actual log fields only.
        """
        logs_text = self._application_logs_as_text(diagnostics)

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
                    evidence=[
                        f"Application logs contain error keywords: {', '.join(matched)}"
                    ],
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
        """
        Generic helper to detect an issue from Kubernetes events.
        """
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

    def _application_logs_as_text(self, diagnostics: Dict[str, Any]) -> str:
        """
        Extract only real application logs.

        Ignores diagnostic collection error fields.
        """
        logs = diagnostics.get("logs") or ""

        if isinstance(logs, str):
            return logs

        if isinstance(logs, list):
            log_lines = []

            for item in logs:
                if isinstance(item, dict) and item.get("log"):
                    log_lines.append(str(item.get("log")))
                elif isinstance(item, str):
                    log_lines.append(item)

            return "\n".join(log_lines)

        if isinstance(logs, dict):
            return "\n".join(
                str(value)
                for key, value in logs.items()
                if key == "log" or not str(key).lower().endswith("error")
            )

        return str(logs)