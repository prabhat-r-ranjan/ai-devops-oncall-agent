"""
Repository Analysis Service.

This service uses FixPlan and GitHubClient to inspect the target file
inside the GitHub repository.

It does not modify files.
It only checks whether the planned fix location exists.
"""

from typing import Any, Dict

from app.clients.github_client import GitHubClient


class RepositoryAnalysisService:
    """
    Performs read-only GitHub repository analysis for a FixPlan.
    """

    def __init__(self):
        self.github_client = GitHubClient()

    def analyze_fix_plan(self, fix_plan: Dict[str, Any]) -> Dict[str, Any]:
        if not self.github_client.is_configured():
            return {
                "enabled": False,
                "status": "GITHUB_NOT_CONFIGURED",
                "message": "GitHub environment variables are missing.",
                "files_checked": [],
            }

        target_file = fix_plan.get("target_file")

        if not target_file:
            return {
                "enabled": True,
                "status": "NO_TARGET_FILE",
                "message": "FixPlan does not contain a target file.",
                "files_checked": [],
            }

        file_result = self.github_client.get_file_content(target_file)

        if not file_result.get("found"):
            return {
                "enabled": True,
                "status": "TARGET_FILE_NOT_FOUND",
                "message": f"Target file '{target_file}' was not found in repository.",
                "files_checked": [target_file],
            }

        file_content = file_result.get("content", "")

        return {
            "enabled": True,
            "status": "TARGET_FILE_FOUND",
            "message": f"Target file '{target_file}' exists in repository.",
            "files_checked": [target_file],
            "target_file": target_file,
            "file_sha": file_result.get("sha"),
            "content": file_content,
            "preview": file_content[:500],
        }