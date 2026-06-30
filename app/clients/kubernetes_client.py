from kubernetes import client, config
from kubernetes.client.rest import ApiException


class KubernetesClient:

    def __init__(self):
        self._load_config()
        self.core_api = client.CoreV1Api()
        self.apps_api = client.AppsV1Api()

    def _load_config(self):
        try:
            config.load_incluster_config()
        except Exception:
            config.load_kube_config()

    def get_deployment_diagnostics(self, namespace: str, deployment_name: str) -> dict:
        try:
            deployment = self.apps_api.read_namespaced_deployment(
                name=deployment_name,
                namespace=namespace
            )

            pods = self._get_pods_for_deployment(namespace, deployment)
            events = self._get_recent_events(namespace)
            logs = self._get_recent_logs(namespace, pods)

            return {
                "namespace": namespace,
                "deployment_name": deployment_name,
                "deployment_status": {
                    "replicas": deployment.status.replicas,
                    "ready_replicas": deployment.status.ready_replicas,
                    "available_replicas": deployment.status.available_replicas,
                    "updated_replicas": deployment.status.updated_replicas,
                },
                "pods": pods,
                "events": events,
                "logs": logs
            }

        except ApiException as e:
            return {
                "namespace": namespace,
                "deployment_name": deployment_name,
                "error": f"Kubernetes API error: {e.reason}",
                "status": e.status
            }
        except Exception as e:
            return {
                "namespace": namespace,
                "deployment_name": deployment_name,
                "error": str(e)
            }

    def _get_pods_for_deployment(self, namespace: str, deployment) -> list:
        selector = deployment.spec.selector.match_labels

        label_selector = ",".join(
            [f"{key}={value}" for key, value in selector.items()]
        )

        pod_list = self.core_api.list_namespaced_pod(
            namespace=namespace,
            label_selector=label_selector
        )

        pods = []

        for pod in pod_list.items:
            container_statuses = pod.status.container_statuses or []

            restart_count = sum(
                container.restart_count for container in container_statuses
            )

            ready = (
                all(container.ready for container in container_statuses)
                if container_statuses
                else False
            )

            pods.append({
                "name": pod.metadata.name,
                "phase": pod.status.phase,
                "ready": ready,
                "restart_count": restart_count,
                "node_name": pod.spec.node_name,
                "pod_ip": pod.status.pod_ip
            })

        return pods

    def _get_recent_events(self, namespace: str) -> list:
        event_list = self.core_api.list_namespaced_event(namespace=namespace)

        sorted_events = sorted(
            event_list.items,
            key=lambda event: (
                event.last_timestamp
                or event.event_time
                or event.metadata.creation_timestamp
            ),
            reverse=True
        )

        events = []

        for event in sorted_events[:10]:
            events.append({
                "type": event.type,
                "reason": event.reason,
                "message": event.message,
                "object": event.involved_object.name,
                "last_timestamp": str(
                    event.last_timestamp
                    or event.event_time
                    or event.metadata.creation_timestamp
                )
            })

        return events

    def _get_recent_logs(self, namespace: str, pods: list) -> list:
        logs = []

        for pod in pods[:3]:
            pod_name = pod["name"]

            try:
                pod_log = self.core_api.read_namespaced_pod_log(
                    name=pod_name,
                    namespace=namespace,
                    tail_lines=50
                )

                if isinstance(pod_log, str) and pod_log.startswith("b'"):
                    pod_log = pod_log[2:-1]
                    pod_log = pod_log.encode("utf-8").decode("unicode_escape")


                logs.append({
                    "pod_name": pod_name,
                    "log": pod_log
                })

            except Exception as e:
                logs.append({
                    "pod_name": pod_name,
                    "error": str(e)
                })

        return logs