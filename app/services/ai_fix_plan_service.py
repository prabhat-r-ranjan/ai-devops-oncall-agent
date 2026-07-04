import json
import os
from typing import Any, Dict

from openai import OpenAI


class AiFixPlanService:
    """
    Uses OpenAI only as a fallback FixPlan generator.

    AI does not directly modify code or raise PR.
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

        prompt = self._build_prompt(
            request=request,
            diagnostics=diagnostics,
            rca_result=rca_result,
            rule_based_fix_plan=rule_based_fix_plan,
        )

        try:
            response = self.client.responses.create(
                model=self.model,
                input=prompt,
                temperature=0.2,
            )

            content = response.output_text
            ai_fix_plan = json.loads(content)

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
You are an expert Kubernetes DevOps engineer.

Goal:
Generate a safe FixPlan only if the issue can be fixed by changing Kubernetes YAML manifests.

Important rules:
- Do not invent files.
- Do not create application code fixes.
- Do not expose secrets.
- If unsure, return can_auto_fix=false.
- Return ONLY valid JSON.
- No markdown.
- No explanation outside JSON.

Allowed target files:
- k8s/base/backend-deployment.yaml
- k8s/base/frontend-deployment.yaml
- k8s/base/ai-agent-deployment.yaml
- k8s/base/incident-ingress.yaml
- k8s/base/kustomization.yaml

Expected JSON format:
{{
  "issue_type": "string",
  "can_auto_fix": true,
  "target_file": "string or null",
  "change_type": "string",
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
{json.dumps(diagnostics, indent=2)}

Rule based RCA:
{json.dumps(rca_result, indent=2)}

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
            "k8s/base/incident-ingress.yaml",
            "k8s/base/kustomization.yaml",
        }

        if not isinstance(ai_fix_plan, dict):
            return self._fallback("AI response is not a JSON object.")

        if ai_fix_plan.get("can_auto_fix") is not True:
            ai_fix_plan["source"] = "OPENAI_FALLBACK"
            return ai_fix_plan

        target_file = ai_fix_plan.get("target_file")

        if target_file not in allowed_files:
            return self._fallback(
                f"AI suggested unsupported target file: {target_file}"
            )

        confidence = int(ai_fix_plan.get("confidence", 0))

        if confidence < 70:
            return self._fallback(
                f"AI confidence too low for auto-fix: {confidence}"
            )

        ai_fix_plan["source"] = "OPENAI_FALLBACK"
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