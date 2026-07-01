import yaml
from typing import Dict, Any


class ManifestUpdater:
    def update_manifest(self, file_content: str, fix_plan: Dict[str, Any]) -> Dict[str, Any]:
        if not fix_plan.get("can_auto_fix"):
            return {
                "enabled": True,
                "status": "SKIPPED",
                "message": "FixPlan is not auto-fixable."
            }

        if fix_plan.get("change_type") != "UPDATE_IMAGE_TAG":
            return {
                "enabled": True,
                "status": "UNSUPPORTED_CHANGE_TYPE",
                "message": f"Unsupported change type: {fix_plan.get('change_type')}"
            }

        manifest = yaml.safe_load(file_content)

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
                "message": "No containers found in manifest."
            }

        old_image = containers[0].get("image")

        if not old_image:
            return {
                "enabled": True,
                "status": "NO_IMAGE_FOUND",
                "message": "No image field found in container."
            }

        # For now: replace bad/live image with repo's known valid image logic later.
        # Current updater proves YAML can be safely parsed and rewritten.
        new_image = old_image

        containers[0]["image"] = new_image

        updated_content = yaml.safe_dump(
            manifest,
            sort_keys=False,
            default_flow_style=False
        )

        return {
            "enabled": True,
            "status": "UPDATED_IN_MEMORY",
            "message": "Manifest parsed and updated in memory.",
            "old_image": old_image,
            "new_image": new_image,
            "updated_content": updated_content
        }