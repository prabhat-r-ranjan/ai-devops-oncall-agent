from dataclasses import dataclass, field
from typing import List


@dataclass
class DetectedIssue:
    """
    Represents one detected Kubernetes issue.
    """

    issue_type: str
    severity: str
    score: int
    evidence: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)