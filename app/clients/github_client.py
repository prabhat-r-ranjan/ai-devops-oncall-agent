"""
GitHub client.

This class contains low-level GitHub API operations.

Responsibilities:
- Read repository files.
- List repository files.
- Read recent commits.
- Later: create branch, update file, create pull request.

This class should not decide what fix is needed.
That responsibility belongs to GitAnalyzer or PullRequestService.
"""

import base64
import os
from typing import Any, Dict, List, Optional

import requests


class GitHubClient:
    """
    Low-level client for GitHub repository operations.
    """

    def __init__(
        self,
        owner: Optional[str] = None,
        repo: Optional[str] = None,
        token: Optional[str] = None,
        base_branch: Optional[str] = None,
    ):
        """
        Initialize GitHub client configuration.

        Values can come from constructor or environment variables.
        """
        self.owner = owner or os.getenv("GITHUB_OWNER")
        self.repo = repo or os.getenv("GITHUB_REPO")
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.base_branch = base_branch or os.getenv("GITHUB_BASE_BRANCH", "main")

        self.base_url = "https://api.github.com"
        self.headers = self._build_headers()

    def _build_headers(self) -> Dict[str, str]:
        """
        Build GitHub API headers.
        """
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        return headers

    def is_configured(self) -> bool:
        """
        Check whether required GitHub configuration is available.
        """
        return bool(self.owner and self.repo and self.token)

    def get_file_content(
        self,
        path: str,
        branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Read one file from GitHub repository.

        Returns:
        - path
        - sha
        - decoded content
        """
        branch = branch or self.base_branch

        url = (
            f"{self.base_url}/repos/{self.owner}/{self.repo}"
            f"/contents/{path}?ref={branch}"
        )

        response = requests.get(url, headers=self.headers, timeout=20)

        if response.status_code == 404:
            return {
                "path": path,
                "found": False,
                "error": "File not found",
            }

        response.raise_for_status()
        data = response.json()

        encoded_content = data.get("content", "")
        decoded_content = base64.b64decode(encoded_content).decode("utf-8")

        return {
            "path": path,
            "found": True,
            "sha": data.get("sha"),
            "content": decoded_content,
        }

    def list_repository_files(
        self,
        branch: Optional[str] = None,
    ) -> List[str]:
        """
        List repository files recursively using Git tree API.
        """
        branch = branch or self.base_branch
        branch_info = self.get_branch(branch)

        tree_sha = branch_info["commit"]["commit"]["tree"]["sha"]

        url = (
            f"{self.base_url}/repos/{self.owner}/{self.repo}"
            f"/git/trees/{tree_sha}?recursive=1"
        )

        response = requests.get(url, headers=self.headers, timeout=20)
        response.raise_for_status()

        data = response.json()

        return [
            item["path"]
            for item in data.get("tree", [])
            if item.get("type") == "blob"
        ]

    def get_recent_commits(
        self,
        branch: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Get recent commits from a branch.
        """
        branch = branch or self.base_branch

        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/commits"

        params = {
            "sha": branch,
            "per_page": limit,
        }

        response = requests.get(
            url,
            headers=self.headers,
            params=params,
            timeout=20,
        )
        response.raise_for_status()

        commits = response.json()

        return [
            {
                "sha": commit.get("sha"),
                "message": commit.get("commit", {}).get("message"),
                "author": commit.get("commit", {}).get("author", {}).get("name"),
                "date": commit.get("commit", {}).get("author", {}).get("date"),
            }
            for commit in commits
        ]

    def get_branch(self, branch: Optional[str] = None) -> Dict[str, Any]:
        """
        Get branch details from GitHub.
        """
        branch = branch or self.base_branch

        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/branches/{branch}"

        response = requests.get(url, headers=self.headers, timeout=20)
        response.raise_for_status()

        return response.json()

    def create_branch(
        self,
        new_branch: str,
        from_branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new branch from an existing branch.

        This will be used later before creating a fix commit.
        """
        from_branch = from_branch or self.base_branch
        branch_info = self.get_branch(from_branch)

        base_sha = branch_info["commit"]["sha"]

        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/git/refs"

        payload = {
            "ref": f"refs/heads/{new_branch}",
            "sha": base_sha,
        }

        response = requests.post(
            url,
            headers=self.headers,
            json=payload,
            timeout=20,
        )

        if response.status_code == 422:
            return {
                "created": False,
                "branch": new_branch,
                "message": "Branch already exists",
            }

        response.raise_for_status()

        return {
            "created": True,
            "branch": new_branch,
            "data": response.json(),
        }

    def update_file(
        self,
        path: str,
        content: str,
        branch: str,
        commit_message: str,
    ) -> Dict[str, Any]:
        """
        Update a file and commit the change to a branch.

        Requires existing file SHA.
        """
        existing_file = self.get_file_content(path=path, branch=branch)

        if not existing_file.get("found"):
            return existing_file

        encoded_content = base64.b64encode(
            content.encode("utf-8")
        ).decode("utf-8")

        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/contents/{path}"

        payload = {
            "message": commit_message,
            "content": encoded_content,
            "sha": existing_file["sha"],
            "branch": branch,
        }

        response = requests.put(
            url,
            headers=self.headers,
            json=payload,
            timeout=20,
        )
        response.raise_for_status()

        return response.json()

    def create_pull_request(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a pull request from head_branch into base_branch.
        """
        base_branch = base_branch or self.base_branch

        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/pulls"

        payload = {
            "title": title,
            "body": body,
            "head": head_branch,
            "base": base_branch,
        }

        response = requests.post(
            url,
            headers=self.headers,
            json=payload,
            timeout=20,
        )
        response.raise_for_status()

        return response.json()