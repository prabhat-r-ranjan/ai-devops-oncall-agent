import json
import os
from typing import Any, Dict

from openai import OpenAI


class AiFixPlanService:
    """
    Uses OpenAI only as a fallback FixPlan generator.

    AI does not modify YAML or raise PR.
    AI only returns a structured FixPlan.
    """

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None

    def generate_fix_plan(
        self,
        request: Any,
        diagnostics: Dict[str, Any],
        rca_result: Dict[str, Any],
        rule_based_fix_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not self.client:
            return self._fallback("OPENAI_API_KEY is not configured.")

        try:
            response = self.client.responses.create(
                model=self.model,
                input=self._build_prompt(
                    request=request,
                    diagnostics=diagnostics,
                    rca_result=rca_result,
                    rule_based_fix_plan=rule_based_fix_plan,
                ),
                temperature=0.1,
            )

            ai_fix_plan = json.loads(response.output_text)
            return self._validate(ai_fix_plan, rule_based_fix_plan)

        except Exception as e:
            return self._fallback(f"AI FixPlan generation failed: {str(e)}")

    def _build_prompt(
        self,
        request: Any,
        diagnostics: Dict[str, Any],
        rca_result: Dict[str, Any],
        rule_based_fix_plan: Dict[str, Any],
    ) -> str:
        return f"""
You are a senior Kubernetes DevOps engineer.

Generate a safe FixPlan only when the issue can be fixed by changing Kubernetes YAML.

Allowed change_type values:
- UPDATE_IMAGE_TAG
- UPDATE_MEMORY_LIMIT
- UPDATE_PROBE

Allowed target files:
- k8s/base/backend-deployment.yaml
- k8s/base/frontend-deployment.yaml
- k8s/base/ai-agent-deployment.yaml

Decision rules:
- If logs/events show OOMKilled or memory pressure, use UPDATE_MEMORY_LIMIT.
- If readiness/liveness probe is failing because the app starts slowly, use UPDATE_PROBE.
- If image tag is invalid, use UPDATE_IMAGE_TAG.
- If deployment does not exist, namespace is wrong, RBAC fails, or diagnostics are unavailable, return can_auto_fix=false.
- If issue requires application code change, return can_auto_fix=false.
- Do not invent files.
- Do not expose secrets.
- Return only valid JSON.

Expected JSON:
{{
  "issue_type": "string",
  "can_auto_fix": true,
  "target_file": "string or null",
  "change_type": "UPDATE_MEMORY_LIMIT or UPDATE_PROBE or UPDATE_IMAGE_TAG or MANUAL_REVIEW",
  "reason": "string",
  "confidence": 0,
  "evidence": ["string"],
  "recommended_changes": {{
    "field": "string",
    "action": "string",
    "details": "string"
  }},
  "source": "OPENAI_FALLBACK"
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

Kubernetes diagnostics:
{json.dumps(diagnostics, indent=2)[:6000]}

Rule based RCA:
{json.dumps(rca_result, indent=2)[:3000]}

Rule based FixPlan:
{json.dumps(rule_based_fix_plan, indent=2)}
"""

    def _validate(
        self,
        ai_fix_plan: Dict[str, Any],
        rule_based_fix_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        allowed_files = {
            "k8s/base/backend-deployment.yaml",
            "k8s/base/frontend-deployment.yaml",
            "k8s/base/ai-agent-deployment.yaml",
        }

        allowed_change_types = {
            "UPDATE_IMAGE_TAG",
            "UPDATE_MEMORY_LIMIT",
            "UPDATE_PROBE",
        }

        if not isinstance(ai_fix_plan, dict):
            return self._fallback("AI response is not a JSON object.")

        ai_fix_plan["source"] = "OPENAI_FALLBACK"

        if ai_fix_plan.get("can_auto_fix") is not True:
            ai_fix_plan.setdefault("can_auto_fix", False)
            ai_fix_plan.setdefault("target_file", None)
            ai_fix_plan.setdefault("change_type", "MANUAL_REVIEW")
            ai_fix_plan.setdefault("confidence", 0)
            return ai_fix_plan

        target_file = ai_fix_plan.get("target_file")
        change_type = ai_fix_plan.get("change_type")

        if target_file not in allowed_files:
            return self._fallback(f"Unsupported target file: {target_file}")

        if change_type not in allowed_change_types:
            return self._fallback(f"Unsupported change type: {change_type}")

        confidence = int(ai_fix_plan.get("confidence", 0))
        if confidence < 70:
            return self._fallback(f"AI confidence too low: {confidence}")

        ai_fix_plan["previous_rule_based_fix_plan"] = rule_based_fix_plan
        return ai_fix_plan

    def _fallback(self, reason: str) -> Dict[str, Any]:
        return {
            "issue_type": "UNKNOWN",
            "can_auto_fix": False,
            "target_file": None,
            "change_type": "AI_FIX_PLAN_SKIPPED",
            "reason": reason,
            "confidence": 0,
            "evidence": [],
            "recommended_changes": {
                "action": "Manual review required."
            },
            "source": "OPENAI_FALLBACK",
        }