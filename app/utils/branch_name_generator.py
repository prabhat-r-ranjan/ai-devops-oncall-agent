import re
from datetime import datetime, timezone


def generate_fix_branch(issue_type: str, deployment_name: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    safe_issue = re.sub(r"[^a-zA-Z0-9-]+", "-", issue_type.lower()).strip("-")
    safe_deployment = re.sub(
        r"[^a-zA-Z0-9-]+", "-", deployment_name.lower()
    ).strip("-")

    return f"fix/{safe_issue}-{safe_deployment}-{timestamp}"