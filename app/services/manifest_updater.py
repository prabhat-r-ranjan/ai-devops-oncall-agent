import os
from typing import Any, Dict

import yaml


class ManifestUpdater:
    def update_manifest(self, file_content: str, fix_plan: Dict[str, Any]) -> Dict[str, Any]:
        if not fix_plan.get("can_auto_fix"):
            return self._skipped("FixPlan is not auto-fixable.")

        try:
            manifest = yaml.safe_load(file_content)
        except yaml.YAMLError as e:
            return {
                "enabled": True,
                "status": "INVALID_YAML",
                "message": f"Manifest YAML could not be parsed: {str(e)}",
            }

        if not isinstance(manifest, dict):
            return {
                "enabled": True,
                "status": "INVALID_MANIFEST",
                "message": "Manifest content is empty or not a valid Kubernetes YAML object.",
            }
        change_type = fix_plan.get("change_type")

        containers = (
            manifest.get("spec", {})
            .get("template", {})
            .get("spec", {})
            .get("containers", [])
        )

        if not containers:
            return {
                "enabled": True,
                "status": "NO_CONTAINERS_FOUND",
                "message": "No containers found in manifest.",
            }

        container = containers[0]

        if change_type == "UPDATE_IMAGE_TAG":
            return self._update_image_tag(manifest, container, file_content)

        if change_type == "UPDATE_MEMORY_LIMIT":
            return self._update_memory_limit(manifest, container)

        if change_type == "UPDATE_PROBE":
            return self._update_probe(manifest, container)

        return {
            "enabled": True,
            "status": "UNSUPPORTED_CHANGE_TYPE",
            "message": f"Unsupported change type: {change_type}",
        }

    def _update_image_tag(
        self,
        manifest: Dict[str, Any],
        container: Dict[str, Any],
        file_content: str,
    ) -> Dict[str, Any]:
        old_image = container.get("image")

        if not old_image:
            return {
                "enabled": True,
                "status": "NO_IMAGE_FOUND",
                "message": "No image field found in container.",
                "field": "containers[].image",
            }

        # ✅ STEP 1: Check if it's a demo ImagePullBackOff case
        # Detects wrong-version, error, or invalid tags
        is_demo_image_pull_issue = any([
            "wrong-version" in old_image,
            "error" in old_image.lower(),
            "invalid" in old_image.lower(),
            "wrong" in old_image.lower(),
            old_image.endswith(":") or old_image.endswith(":latest") and "wrong" in old_image,
        ])

        if is_demo_image_pull_issue:
            # ✅ Demo specific fix: Extract base image name and add :latest
            # Examples:
            # nginx:wrong-version → nginx:latest
            # myapp:error-tag → myapp:latest
            # app:v1.0-invalid → app:latest
            base_image = old_image.split(":")[0]
            new_image = f"{base_image}:latest"

            # Special case: If image is from ACR, preserve registry
            if "/" in old_image and not old_image.startswith("prabhatcr001.azurecr.io/demo"):
                # Keep registry prefix if present
                registry_parts = old_image.split("/")
                if len(registry_parts) > 1:
                    # Example: myregistry.azurecr.io/app:wrong → myregistry.azurecr.io/app:latest
                    registry = "/".join(registry_parts[:-1])
                    image_name = registry_parts[-1].split(":")[0]
                    new_image = f"{registry}/{image_name}:latest"

            # Check if already fixed
            if old_image == new_image:
                return {
                    "enabled": True,
                    "status": "NO_CHANGE_NEEDED",
                    "message": "Image tag already appears to be correct.",
                    "field": "containers[].image",
                    "old_value": old_image,
                    "new_value": new_image,
                    "old_image": old_image,
                    "new_image": new_image,
                    "updated_content": file_content,
                }

            # Apply the fix
            container["image"] = new_image

            return {
                "enabled": True,
                "status": "UPDATED_IN_MEMORY",
                "message": f"Fixed invalid image tag: {old_image} → {new_image}",
                "field": "containers[].image",
                "old_value": old_image,
                "new_value": new_image,
                "old_image": old_image,
                "new_image": new_image,
                "fix_type": "DEMO_IMAGE_PULL_FIX",
                "updated_content": self._dump(manifest),
            }

        # ✅ STEP 2: Production fix using environment variable
        new_image = os.getenv("DEFAULT_BACKEND_IMAGE")

        if not new_image:
            # ✅ Log the issue but don't fail
            print(f"⚠️ DEFAULT_BACKEND_IMAGE not set. Using current image: {old_image}")
            return {
                "enabled": True,
                "status": "NO_IMAGE_UPDATE",
                "message": "DEFAULT_BACKEND_IMAGE environment variable is missing. Keeping current image.",
                "old_value": old_image,
                "field": "containers[].image",
                "updated_content": file_content,
            }

        # ✅ STEP 3: Check if already up to date
        if old_image == new_image:
            return {
                "enabled": True,
                "status": "NO_CHANGE_NEEDED",
                "message": "Manifest already contains the expected image.",
                "field": "containers[].image",
                "old_value": old_image,
                "new_value": new_image,
                "old_image": old_image,
                "new_image": new_image,
                "updated_content": file_content,
            }

        # ✅ STEP 4: Apply production fix
        container["image"] = new_image

        return {
            "enabled": True,
            "status": "UPDATED_IN_MEMORY",
            "message": f"Updated image: {old_image} → {new_image}",
            "field": "containers[].image",
            "old_value": old_image,
            "new_value": new_image,
            "old_image": old_image,
            "new_image": new_image,
            "fix_type": "ENV_BASED_IMAGE_UPDATE",
            "updated_content": self._dump(manifest),
        }

    def _update_memory_limit(
        self,
        manifest: Dict[str, Any],
        container: Dict[str, Any],
    ) -> Dict[str, Any]:
        resources = container.setdefault("resources", {})
        limits = resources.setdefault("limits", {})

        old_memory = limits.get("memory")
        new_memory = os.getenv("DEFAULT_MEMORY_LIMIT", "768Mi")

        if old_memory == new_memory:
            return {
                "enabled": True,
                "status": "NO_CHANGE_NEEDED",
                "message": "Manifest already contains the expected memory limit.",
                "field": "resources.limits.memory",
                "old_value": old_memory,
                "new_value": new_memory,
                "updated_content": self._dump(manifest),
            }

        limits["memory"] = new_memory

        return {
            "enabled": True,
            "status": "UPDATED_IN_MEMORY",
            "message": "Memory limit updated in memory.",
            "field": "resources.limits.memory",
            "old_value": old_memory,
            "new_value": new_memory,
            "old_memory": old_memory,
            "new_memory": new_memory,
            "updated_content": self._dump(manifest),
        }

    def _update_probe(
        self,
        manifest: Dict[str, Any],
        container: Dict[str, Any],
    ) -> Dict[str, Any]:
        readiness_probe = container.setdefault("readinessProbe", {})
        liveness_probe = container.setdefault("livenessProbe", {})

        old_readiness_delay = readiness_probe.get("initialDelaySeconds")
        old_liveness_delay = liveness_probe.get("initialDelaySeconds")
        old_timeout = readiness_probe.get("timeoutSeconds")

        new_readiness_delay = int(os.getenv("DEFAULT_READINESS_INITIAL_DELAY", "30"))
        new_liveness_delay = int(os.getenv("DEFAULT_LIVENESS_INITIAL_DELAY", "90"))
        new_timeout = int(os.getenv("DEFAULT_PROBE_TIMEOUT", "5"))

        readiness_probe["initialDelaySeconds"] = new_readiness_delay
        readiness_probe["timeoutSeconds"] = new_timeout

        liveness_probe["initialDelaySeconds"] = new_liveness_delay
        liveness_probe["timeoutSeconds"] = new_timeout

        return {
            "enabled": True,
            "status": "UPDATED_IN_MEMORY",
            "message": "Probe configuration updated in memory.",
            "field": "readinessProbe/livenessProbe",
            "old_value": {
                "readiness_initial_delay": old_readiness_delay,
                "liveness_initial_delay": old_liveness_delay,
                "timeout": old_timeout,
            },
            "new_value": {
                "readiness_initial_delay": new_readiness_delay,
                "liveness_initial_delay": new_liveness_delay,
                "timeout": new_timeout,
            },
            "updated_content": self._dump(manifest),
        }

    def _skipped(self, message: str) -> Dict[str, Any]:
        return {
            "enabled": True,
            "status": "SKIPPED",
            "message": message,
        }

    def _dump(self, manifest: Dict[str, Any]) -> str:
        return yaml.safe_dump(
            manifest,
            sort_keys=False,
            default_flow_style=False,
        )