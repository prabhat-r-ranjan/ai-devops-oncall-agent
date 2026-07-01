from typing import Any, Dict

from app.clients.github_client import GitHubClient
from app.utils.branch_name_generator import generate_fix_branch


class PullRequestService:
    """
    Orchestrates branch creation, file update, and pull request creation.

    This service decides how to convert a manifest_update result into a PR.
    """

    def __init__(self):
        self.github_client = GitHubClient()

    def create_fix_pr(
        self,
        fix_plan: Dict[str, Any],
        repository_analysis: Dict[str, Any],
        manifest_update: Dict[str, Any],
        deployment_name: str,
    ) -> Dict[str, Any]:
        if not fix_plan.get("can_auto_fix"):
            return {
                "enabled": True,
                "status": "SKIPPED",
                "message": "FixPlan is not auto-fixable.",
            }

        if repository_analysis.get("status") != "TARGET_FILE_FOUND":
            return {
                "enabled": True,
                "status": "SKIPPED",
                "message": "Target file was not found in repository.",
            }

        if manifest_update.get("status") != "UPDATED_IN_MEMORY":
            return {
                "enabled": True,
                "status": "SKIPPED",
                "message": "Manifest was not updated in memory.",
            }

        target_file = repository_analysis.get("target_file")
        updated_content = manifest_update.get("updated_content")

        if not target_file or not updated_content:
            return {
                "enabled": True,
                "status": "SKIPPED",
                "message": "Missing target file or updated content.",
            }

        old_image = manifest_update.get("old_image")
        new_image = manifest_update.get("new_image")

        if old_image == new_image:
            return {
                "enabled": True,
                "status": "NO_CHANGE_NEEDED",
                "message": (
                    "Repository manifest already contains the expected image. "
                    "This looks like cluster drift, not a repository manifest issue."
                ),
                "target_file": target_file,
                "old_image": old_image,
                "new_image": new_image,
                "recommended_action": "Rollback deployment or sync from GitOps source.",
            }

        branch_name = generate_fix_branch(
            issue_type=fix_plan.get("issue_type", "unknown"),
            deployment_name=deployment_name,
        )

        self.github_client.create_branch(branch_name)

        commit_message = f"Fix image tag for {deployment_name}"

        self.github_client.update_file(
            path=target_file,
            content=updated_content,
            branch=branch_name,
            commit_message=commit_message,
        )

        pr_title = f"Fix {fix_plan.get('issue_type')} for {deployment_name}"

        pr_body = f"""
## AI DevOps On-Call Agent Fix

### Issue
{fix_plan.get("issue_type")}

### Reason
{fix_plan.get("reason")}

### Change
Updated Kubernetes manifest:

`{target_file}`

### Image Change
- Old: `{old_image}`
- New: `{new_image}`

### Confidence
{fix_plan.get("confidence")}
""".strip()

        pr = self.github_client.create_pull_request(
            title=pr_title,
            body=pr_body,
            head_branch=branch_name,
        )

        return {
            "enabled": True,
            "status": "PR_CREATED",
            "branch": branch_name,
            "target_file": target_file,
            "pr_url": pr.get("html_url"),
            "pr_number": pr.get("number"),
            "commit_message": commit_message,
        }