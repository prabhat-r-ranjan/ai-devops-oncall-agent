"""
Fix plan model.

A FixPlan represents what the agent thinks should be changed
before it creates a Git branch, commit, or pull request.

This model does not modify files.
It only describes the planned fix.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FixPlan:
    """
    Represents a planned remediation action.
    """

    issue_type: str
    can_auto_fix: bool
    target_file: Optional[str]
    change_type: str
    reason: str
    confidence: int
    evidence: List[str] = field(default_factory=list)
    recommended_changes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert FixPlan to dictionary so it can be returned in API response.
        """
        return {
            "issue_type": self.issue_type,
            "can_auto_fix": self.can_auto_fix,
            "target_file": self.target_file,
            "change_type": self.change_type,
            "reason": self.reason,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "recommended_changes": self.recommended_changes,
        }