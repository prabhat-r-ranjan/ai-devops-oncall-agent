import json
import os
from typing import Any, Dict

from openai import OpenAI


class AiFixPlanReviewerService:
    """
    Reviews the final FixPlan before PR creation.

    This service does not block PR creation.
    It only provides AI review metadata for audit/demo purpose.
    """

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None

    def review_fix_plan(
        self,
        request: Any,
        diagnostics: Dict[str, Any],
        rca_result: Dict[str, Any],
        fix_plan: Dict[str, Any],
        repository_analysis: Dict[str, Any],
        manifest_update: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not self.client:
            return self._fallback("OPENAI_API_KEY is not configured.")

        if not fix_plan.get("can_auto_fix"):
            return self._fallback("FixPlan is not auto-fixable.")

        if repository_analysis.get("status") != "TARGET_FILE_FOUND":
            return self._fallback("Target file was not found in repository.")

        if manifest_update.get("status") != "UPDATED_IN_MEMORY":
            return self._fallback("Manifest was not updated in memory.")

        try:
            response = self.client.responses.create(
                model=self.model,
                input=self._build_prompt(
                    request=request,
                    diagnostics=diagnostics,
                    rca_result=rca_result,
                    fix_plan=fix_plan,
                    repository_analysis=repository_analysis,
                    manifest_update=manifest_update,
                ),
                temperature=0.1,
            )

            review = json.loads(response.output_text)
            return self._validate(review)

        except Exception as e:
            return self._fallback(f"AI review failed: {str(e)}")

    def _build_prompt(
        self,
        request: Any,
        diagnostics: Dict[str, Any],
        rca_result: Dict[str, Any],
        fix_plan: Dict[str, Any],
        repository_analysis: Dict[str, Any],
        manifest_update: Dict[str, Any],
    ) -> str:
        repo_preview = repository_analysis.get("preview", "")
        updated_preview = manifest_update.get("updated_content", "")[:1500]

        return f"""
You are a senior Kubernetes DevOps reviewer.

Review the proposed automated FixPlan before a pull request is created.

Rules:
- Do not modify YAML.
- Do not invent repository files.
- Do not expose secrets.
- Return only valid JSON.
- No markdown.
- If the fix is reasonable and low-risk, approve it.
- If the issue and fix do not match, mark approved=false.

Expected JSON format:
{{
  "approved": true,
  "risk": "LOW",
  "confidence": 90,
  "review_summary": "string",
  "why_this_fix_is_safe": "string",
  "additional_checks": ["string"],
  "source": "OPENAI_REVIEWER"
}}

Incident:
{{
  "incident_id": "{request.incident_id}",
  "title": "{request.title}",
  "description": "{request.description}",
  "severity": "{request.severity}",
  "namespace": "{request.namespace}",
  "deployment_name": "{request.deployment_name}",
  "service_name": "{request.service_name}"
}}

RCA Result:
{json.dumps(rca_result, indent=2)[:2500]}

Final FixPlan:
{json.dumps(fix_plan, indent=2)}

Diagnostics summary:
{json.dumps(diagnostics, indent=2)[:2500]}

Repository file preview:
{repo_preview}

Manifest update result:
{json.dumps(manifest_update, indent=2, default=str)[:1500]}

Updated manifest preview:
{updated_preview}
"""

    def _validate(self, review: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(review, dict):
            return self._fallback("AI review response is not a JSON object.")

        review.setdefault("approved", False)
        review.setdefault("risk", "UNKNOWN")
        review.setdefault("confidence", 0)
        review.setdefault("review_summary", "No review summary provided.")
        review.setdefault("why_this_fix_is_safe", "Not provided.")
        review.setdefault("additional_checks", [])
        review["source"] = "OPENAI_REVIEWER"

        return review

    def _fallback(self, reason: str) -> Dict[str, Any]:
        return {
            "approved": False,
            "risk": "UNKNOWN",
            "confidence": 0,
            "review_summary": reason,
            "why_this_fix_is_safe": "AI review was not available.",
            "additional_checks": ["Review the generated PR manually."],
            "source": "OPENAI_REVIEWER",
        }
