from kubernetes import client, config

config.load_kube_config()

core_api = client.CoreV1Api()

pods = core_api.list_namespaced_pod(namespace="default")

for pod in pods.items:
    print(pod.metadata.name, pod.status.phase)