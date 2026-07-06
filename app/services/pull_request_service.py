from typing import Any, Dict, Optional

from app.clients.github_client import GitHubClient
from app.utils.branch_name_generator import generate_fix_branch


class PullRequestService:
    """
    Creates a Git branch, commits manifest changes, and opens a Pull Request.

    Supports generic manifest changes such as:
    - image tag updates
    - memory limit updates
    - probe configuration updates

    AI review is optional and is added to the PR description when available.
    """

    def __init__(self):
        self.github_client = GitHubClient()

    def create_fix_pr(
        self,
        fix_plan: Dict[str, Any],
        repository_analysis: Dict[str, Any],
        manifest_update: Dict[str, Any],
        deployment_name: str,
        ai_review: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a GitHub pull request from an in-memory manifest update.

        This method does not decide the fix.
        It only creates a PR when:
        - FixPlan is auto-fixable
        - target file exists
        - manifest was updated in memory
        """

        validation_error = self._validate_pr_inputs(
            fix_plan=fix_plan,
            repository_analysis=repository_analysis,
            manifest_update=manifest_update,
        )

        if validation_error:
            return validation_error

        target_file = repository_analysis.get("target_file")
        updated_content = manifest_update.get("updated_content")

        field = manifest_update.get("field", "unknown")
        old_value = manifest_update.get("old_value")
        new_value = manifest_update.get("new_value")

        if old_value == new_value:
            return {
                "enabled": True,
                "status": "NO_CHANGE_NEEDED",
                "message": (
                    "Repository manifest already contains the expected value. "
                    "This looks like cluster drift or a no-op fix."
                ),
                "target_file": target_file,
                "field": field,
                "old_value": old_value,
                "new_value": new_value,
                "recommended_action": "Rollback deployment or sync from GitOps source.",
            }

        branch_name = generate_fix_branch(
            issue_type=fix_plan.get("issue_type", "unknown"),
            deployment_name=deployment_name,
        )

        self.github_client.create_branch(branch_name)

        commit_message = self._build_commit_message(
            fix_plan=fix_plan,
            deployment_name=deployment_name,
        )

        self.github_client.update_file(
            path=target_file,
            content=updated_content,
            branch=branch_name,
            commit_message=commit_message,
        )

        pr_title = self._build_pr_title(
            fix_plan=fix_plan,
            deployment_name=deployment_name,
        )

        pr_body = self._build_pr_body(
            fix_plan=fix_plan,
            target_file=target_file,
            field=field,
            old_value=old_value,
            new_value=new_value,
            ai_review=ai_review,
        )

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
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
            "pr_url": pr.get("html_url"),
            "pr_number": pr.get("number"),
            "commit_message": commit_message,
            "ai_review": ai_review or {},
        }

    def _validate_pr_inputs(
        self,
        fix_plan: Dict[str, Any],
        repository_analysis: Dict[str, Any],
        manifest_update: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Validate whether PR creation can proceed.
        """

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

        return None

    def _build_commit_message(
        self,
        fix_plan: Dict[str, Any],
        deployment_name: str,
    ) -> str:
        issue_type = fix_plan.get("issue_type", "UNKNOWN")
        return f"Fix {issue_type} for {deployment_name}"

    def _build_pr_title(
        self,
        fix_plan: Dict[str, Any],
        deployment_name: str,
    ) -> str:
        issue_type = fix_plan.get("issue_type", "UNKNOWN")
        return f"Fix {issue_type} for {deployment_name}"

    def _build_pr_body(
        self,
        fix_plan: Dict[str, Any],
        target_file: str,
        field: str,
        old_value: Any,
        new_value: Any,
        ai_review: Optional[Dict[str, Any]],
    ) -> str:
        ai_review_section = self._build_ai_review_section(ai_review)

        return f"""
# AI DevOps On-Call Agent

## Issue

{fix_plan.get("issue_type")}

## Root Cause

{fix_plan.get("reason")}

## Target File

`{target_file}`

## Change Type

`{fix_plan.get("change_type")}`

## Updated Field

`{field}`

## Previous Value

```text
{old_value}
```

## Updated Value

```text
{new_value}
```

## FixPlan Confidence

{fix_plan.get("confidence")}

---

{ai_review_section}
""".strip()

    def _build_ai_review_section(
        self,
        ai_review: Optional[Dict[str, Any]],
    ) -> str:
        review = ai_review or {}

        additional_checks = review.get("additional_checks") or []
        additional_checks_text = "\n".join(
            f"- {item}" for item in additional_checks
        )

        if not additional_checks_text:
            additional_checks_text = (
                "- Review the generated manifest before merge.\n"
                "- Validate the change in a staging or test cluster.\n"
                "- Monitor rollout status after merge."
            )

        return f"""
## AI Review

**Approved:** {review.get("approved")}

**Risk:** {review.get("risk")}

**AI Confidence:** {review.get("confidence")}

### Review Summary

{review.get("review_summary")}

### Why This Fix Is Safe

{review.get("why_this_fix_is_safe")}

### Additional Checks

{additional_checks_text}
""".strip()
