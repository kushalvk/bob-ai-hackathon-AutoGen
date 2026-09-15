"""LLM Client abstraction for ClinGuard AI severity classification.

Provides a pluggable interface for LLM-based severity review of ambiguous
protocol deviations. Supports watsonx.ai and OpenAI-compatible endpoints.

The real client is activated by setting the LLM_PROVIDER environment variable.
When LLM_PROVIDER is unset or empty, the system runs in pure deterministic mode.
A MockLLMClient is provided for unit tests (no network access required).
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ICH E6(R2) severity definitions included in every LLM prompt
ICH_E6_SEVERITY_DEFINITIONS = """
ICH E6(R2) GCP Severity Definitions:
- Major: Impacts patient safety, rights, or the reliability/integrity of trial data
  (e.g., banned co-med causing a safety interaction, dosing error affecting efficacy data).
- Minor: Does not significantly impact patient safety or data integrity
  (e.g., visit conducted a couple of days outside window, no clinical impact).
- Administrative: Process/paperwork issue with no safety or data impact
  (e.g., missing signature date on an otherwise complete form).
"""


def _build_classification_prompt(deviation_context: Dict[str, Any]) -> str:
    """Build the LLM prompt for severity classification review.

    Constructs a structured prompt containing the deviation details, evidence,
    current rule-based severity, and ICH E6(R2) definitions. Instructs the LLM
    to return a JSON object with severity and rationale.

    Args:
        deviation_context: Dictionary containing deviation type, evidence,
            and the current default_severity from deterministic rules.

    Returns:
        A formatted prompt string for the LLM.
    """
    return f"""You are a clinical trial protocol deviation severity classifier.
Review the following deviation and determine the appropriate severity level.

{ICH_E6_SEVERITY_DEFINITIONS}

Deviation Details:
- Type: {deviation_context.get('type', 'unknown')}
- Current Rule-Based Severity: {deviation_context.get('default_severity', 'unknown')}
- Evidence: {json.dumps(deviation_context.get('evidence', {}), indent=2, default=str)}
- Existing Rationale: {deviation_context.get('severity_rationale', '')}

Instructions:
1. Evaluate whether the rule-based severity is appropriate given the clinical context.
2. You may override the severity if the evidence warrants it.
3. Provide a 1-2 sentence rationale citing the relevant ICH E6(R2) principle.
4. Respond with ONLY a valid JSON object in this exact format:

{{"severity": "major|minor|administrative", "rationale": "Your 1-2 sentence rationale citing ICH E6(R2)."}}
"""


class BaseLLMClient(ABC):
    """Abstract base class for LLM severity classification clients.

    All LLM client implementations must subclass this and implement
    the classify_severity method.
    """

    @abstractmethod
    def classify_severity(self, deviation_context: Dict[str, Any]) -> Dict[str, str]:
        """Classify the severity of an ambiguous deviation using an LLM.

        Args:
            deviation_context: Dictionary containing:
                - type (str): Deviation type (e.g., 'missed_visit')
                - default_severity (str): Rule-based default severity
                - evidence (dict): Structured evidence from the detection engine
                - severity_rationale (str): Existing rationale from rules

        Returns:
            Dictionary with:
                - severity (str): 'major', 'minor', or 'administrative'
                - rationale (str): 1-2 sentence rationale citing ICH E6(R2)
        """
        ...


class WatsonXClient(BaseLLMClient):
    """Real LLM client using IBM watsonx.ai foundation models.

    Requires environment variables:
        WATSONX_API_KEY: IBM Cloud API key
        WATSONX_PROJECT_ID: watsonx.ai project ID
        WATSONX_URL: watsonx.ai endpoint URL (default: us-south)
        WATSONX_MODEL_ID: Model to use (default: ibm/granite-13b-instruct-v2)
    """

    def __init__(self) -> None:
        """Initialize WatsonXClient with credentials from environment variables.

        Raises:
            ImportError: If ibm-watsonx-ai package is not installed.
            ValueError: If required environment variables are missing.
        """
        self.api_key = os.getenv("WATSONX_API_KEY", "")
        self.project_id = os.getenv("WATSONX_PROJECT_ID", "")
        self.url = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
        self.model_id = os.getenv("WATSONX_MODEL_ID", "ibm/granite-13b-instruct-v2")

        if not self.api_key or not self.project_id:
            raise ValueError(
                "WATSONX_API_KEY and WATSONX_PROJECT_ID environment variables "
                "are required for WatsonXClient."
            )

        try:
            from ibm_watsonx_ai.foundation_models import Model
            from ibm_watsonx_ai.credentials import Credentials

            credentials = Credentials(url=self.url, api_key=self.api_key)
            self.model = Model(
                model_id=self.model_id,
                credentials=credentials,
                project_id=self.project_id,
                params={
                    "max_new_tokens": 256,
                    "temperature": 0.1,
                    "top_p": 0.95,
                },
            )
            logger.info(
                "WatsonXClient initialized with model '%s' at '%s'",
                self.model_id,
                self.url,
            )
        except ImportError:
            raise ImportError(
                "ibm-watsonx-ai package is required for WatsonXClient. "
                "Install it with: pip install ibm-watsonx-ai"
            )

    def classify_severity(self, deviation_context: Dict[str, Any]) -> Dict[str, str]:
        """Classify severity using IBM watsonx.ai foundation model.

        Sends the deviation context to the watsonx.ai model and parses the
        JSON response containing severity and rationale.

        Args:
            deviation_context: Deviation details including type, evidence,
                and current rule-based severity.

        Returns:
            Dictionary with 'severity' and 'rationale' keys.
            Falls back to default severity on any LLM error.
        """
        prompt = _build_classification_prompt(deviation_context)
        try:
            response = self.model.generate_text(prompt)
            result = json.loads(response.strip())
            severity = result.get("severity", "").lower()
            if severity not in ("major", "minor", "administrative"):
                logger.warning(
                    "LLM returned invalid severity '%s', falling back to default",
                    severity,
                )
                return {
                    "severity": deviation_context["default_severity"],
                    "rationale": deviation_context.get("severity_rationale", ""),
                }
            return {
                "severity": severity,
                "rationale": result.get("rationale", ""),
            }
        except (json.JSONDecodeError, KeyError, Exception) as e:
            logger.error("WatsonX LLM call failed: %s. Falling back to deterministic.", e)
            return {
                "severity": deviation_context["default_severity"],
                "rationale": deviation_context.get("severity_rationale", ""),
            }


class MockLLMClient(BaseLLMClient):
    """Deterministic mock LLM client for unit tests.

    Returns predictable severity overrides without network access.
    Simulates the LLM reviewing ambiguous cases and producing rationales
    that cite ICH E6(R2) principles.
    """

    def classify_severity(self, deviation_context: Dict[str, Any]) -> Dict[str, str]:
        """Return a deterministic severity classification for testing.

        Mock logic:
        - missed_visit with days_outside_window <= 3: overrides to 'minor'
          (borderline, no clinical impact)
        - missed_visit with days_outside_window > 3: overrides to 'major'
          (significant delay impacts data)
        - wrong_dose with percentage_deviation <= 10: overrides to 'minor'
          (clinically insignificant variation)
        - All other ambiguous cases: returns the default_severity unchanged

        Args:
            deviation_context: Deviation details for classification.

        Returns:
            Dictionary with deterministic 'severity' and 'rationale'.
        """
        dev_type = deviation_context.get("type", "")
        evidence = deviation_context.get("evidence", {})
        delta = evidence.get("delta", {})
        default = deviation_context.get("default_severity", "minor")

        if dev_type == "missed_visit":
            days_outside = 0
            if isinstance(delta, dict):
                days_outside = abs(delta.get("days_outside_window", 0))

            if days_outside <= 3:
                return {
                    "severity": "minor",
                    "rationale": (
                        "Per ICH E6(R2) §4.5, a visit marginally outside the "
                        "protocol window (≤3 days) does not significantly impact "
                        "patient safety or data integrity. Classified as minor."
                    ),
                }
            else:
                return {
                    "severity": "major",
                    "rationale": (
                        "Per ICH E6(R2) §4.5 and §6.4, a visit conducted "
                        f"{days_outside} days outside the protocol window "
                        "impacts the reliability of trial data. Classified as major."
                    ),
                }

        if dev_type == "wrong_dose":
            pct_dev = 0
            if isinstance(delta, dict):
                pct_dev = delta.get("percentage_deviation", 0)

            if pct_dev <= 10:
                return {
                    "severity": "minor",
                    "rationale": (
                        "Per ICH E6(R2) §4.5, a dose deviation of ≤10% is "
                        "clinically insignificant and does not impact data "
                        "integrity. Classified as minor."
                    ),
                }

        # Default: return the rule-based severity
        return {
            "severity": default,
            "rationale": (
                f"Per ICH E6(R2), the default severity of '{default}' is "
                "appropriate for this deviation type based on clinical context."
            ),
        }


def get_llm_client() -> Optional[BaseLLMClient]:
    """Factory function to create the appropriate LLM client.

    Reads the LLM_PROVIDER environment variable to determine which client
    to instantiate:
    - 'watsonx': Returns a WatsonXClient (requires watsonx credentials)
    - '' or unset: Returns None (pure deterministic mode)

    Returns:
        A BaseLLMClient instance, or None if no LLM provider is configured.
    """
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()

    if provider == "watsonx":
        logger.info("LLM_PROVIDER=watsonx — initializing WatsonXClient")
        return WatsonXClient()

    if provider:
        logger.warning("Unknown LLM_PROVIDER '%s' — running in deterministic mode", provider)

    return None
