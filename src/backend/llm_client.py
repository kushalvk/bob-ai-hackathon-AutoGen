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
from typing import Any, Dict, List, Optional

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


def _build_capa_prompt(deviation_summaries: List[Dict[str, Any]]) -> str:
    """Build the LLM prompt for CAPA narrative generation.

    Constructs a prompt listing clustered deviation details and instructs
    the LLM to produce root cause analysis, corrective action, and preventive
    action narratives. Only these three narrative fields are LLM-authored;
    all other CAPA fields are determined deterministically.

    Args:
        deviation_summaries: List of dictionaries, each containing:
            - type (str): Deviation type
            - severity (str): Severity level
            - severity_rationale (str): Rationale for severity
            - evidence (dict): Structured evidence from detection

    Returns:
        A formatted prompt string for the LLM.
    """
    deviations_text = ""
    for i, dev in enumerate(deviation_summaries, 1):
        deviations_text += f"""
Deviation {i}:
- Type: {dev.get('type', 'unknown')}
- Severity: {dev.get('severity', 'unknown')}
- Rationale: {dev.get('severity_rationale', '')}
- Evidence: {json.dumps(dev.get('evidence', {}), indent=2, default=str)}
"""

    return f"""You are a clinical trial quality management specialist drafting a
Corrective and Preventive Action (CAPA) report for protocol deviations.

The following related deviation(s) have been identified:
{deviations_text}

Based on these deviations, provide:
1. A root cause analysis explaining WHY these deviations occurred.
2. A corrective action describing the IMMEDIATE steps to address the deviation(s).
3. A preventive action describing LONG-TERM process changes to prevent recurrence.

Each response should be 2-4 sentences, professional, and cite relevant ICH E6(R2) principles.

Respond with ONLY a valid JSON object in this exact format:
{{"root_cause": "Your root cause analysis.", "corrective_action": "Your corrective action.", "preventive_action": "Your preventive action."}}
"""


class BaseLLMClient(ABC):
    """Abstract base class for LLM severity classification clients.

    All LLM client implementations must subclass this and implement
    the classify_severity and generate_capa_narrative methods.
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

    @abstractmethod
    def generate_capa_narrative(
        self, deviation_summaries: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """Generate the three LLM-authored narrative fields for a CAPA report.

        Only root_cause, corrective_action, and preventive_action are produced
        by the LLM. All other CAPA fields (finding, severity, owner, dates)
        are determined deterministically from existing data.

        Args:
            deviation_summaries: List of deviation detail dicts, each with:
                - type (str): Deviation type
                - severity (str): Severity level
                - severity_rationale (str): Rationale for severity
                - evidence (dict): Structured evidence from detection

        Returns:
            Dictionary with exactly three keys:
                - root_cause (str): Root cause analysis narrative
                - corrective_action (str): Immediate corrective action narrative
                - preventive_action (str): Long-term preventive action narrative
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

    def generate_capa_narrative(
        self, deviation_summaries: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """Generate CAPA narrative fields using IBM watsonx.ai foundation model.

        Sends deviation summaries to the model and parses the JSON response
        containing root_cause, corrective_action, and preventive_action.

        Args:
            deviation_summaries: List of deviation detail dicts.

        Returns:
            Dictionary with root_cause, corrective_action, preventive_action.
            Falls back to generic text on any LLM error.
        """
        prompt = _build_capa_prompt(deviation_summaries)
        fallback = _capa_narrative_fallback(deviation_summaries)
        try:
            response = self.model.generate_text(prompt)
            result = json.loads(response.strip())
            # Validate all three keys present
            for key in ("root_cause", "corrective_action", "preventive_action"):
                if key not in result or not result[key]:
                    logger.warning(
                        "LLM CAPA response missing '%s', using fallback", key
                    )
                    return fallback
            return {
                "root_cause": result["root_cause"],
                "corrective_action": result["corrective_action"],
                "preventive_action": result["preventive_action"],
            }
        except (json.JSONDecodeError, KeyError, Exception) as e:
            logger.error(
                "WatsonX CAPA narrative generation failed: %s. Using fallback.", e
            )
            return fallback


# ---------------------------------------------------------------------------
# Deterministic fallback narratives (used when no LLM is available)
# ---------------------------------------------------------------------------

_FALLBACK_NARRATIVES: Dict[str, Dict[str, str]] = {
    "missed_visit": {
        "root_cause": (
            "Scheduling process gaps and insufficient visit window tracking led to "
            "patient visits occurring outside the protocol-defined windows."
        ),
        "corrective_action": (
            "Retrain site staff on visit scheduling procedures and implement automated "
            "visit window reminders for upcoming patient appointments."
        ),
        "preventive_action": (
            "Deploy an electronic visit tracking system with automated alerts 7 days "
            "before visit windows close, and establish monthly compliance audits."
        ),
    },
    "wrong_dose": {
        "root_cause": (
            "Inadequate dose verification procedures at the dispensing stage allowed "
            "incorrect dosages to be administered to trial participants."
        ),
        "corrective_action": (
            "Implement immediate double-verification of all dose calculations and "
            "re-train pharmacy and nursing staff on protocol dosing requirements."
        ),
        "preventive_action": (
            "Introduce an electronic dose calculation and verification system with "
            "built-in protocol dose range checks prior to dispensing."
        ),
    },
    "banned_comed": {
        "root_cause": (
            "Insufficient concomitant medication screening and lack of real-time "
            "prohibited medication alerts during patient care."
        ),
        "corrective_action": (
            "Review and discontinue the prohibited concomitant medication immediately. "
            "Assess patient safety and report as required per protocol."
        ),
        "preventive_action": (
            "Integrate the protocol's prohibited medication list into the site's "
            "electronic health record system with automated interaction alerts."
        ),
    },
    "eligibility_breach": {
        "root_cause": (
            "Incomplete eligibility verification at screening allowed a participant "
            "who did not meet all inclusion/exclusion criteria to be enrolled."
        ),
        "corrective_action": (
            "Perform a retrospective eligibility review for the affected participant "
            "and notify the sponsor and IRB/IEC as required."
        ),
        "preventive_action": (
            "Implement a mandatory dual-sign-off eligibility checklist and add "
            "electronic eligibility verification at the point of enrollment."
        ),
    },
    "documentation": {
        "root_cause": (
            "Administrative documentation procedures were not consistently followed, "
            "resulting in missing or incomplete trial records."
        ),
        "corrective_action": (
            "Complete and correct all missing documentation entries. "
            "Conduct a documentation compliance review at the affected site."
        ),
        "preventive_action": (
            "Establish regular documentation audits and provide refresher training "
            "on GCP documentation requirements per ICH E6(R2)."
        ),
    },
}

_DEFAULT_FALLBACK = {
    "root_cause": (
        "Process or procedural gaps at the site led to protocol non-compliance. "
        "A detailed investigation is needed to identify specific contributing factors."
    ),
    "corrective_action": (
        "Conduct an immediate review of the deviation circumstances, retrain "
        "relevant staff, and implement interim corrective measures."
    ),
    "preventive_action": (
        "Establish enhanced monitoring and periodic compliance audits to prevent "
        "recurrence. Update SOPs as needed based on investigation findings."
    ),
}


def _capa_narrative_fallback(
    deviation_summaries: List[Dict[str, Any]],
) -> Dict[str, str]:
    """Return deterministic fallback CAPA narrative text.

    Selects the most appropriate canned narrative based on the primary
    deviation type in the cluster. Used when no LLM client is available
    or when the LLM call fails.

    Args:
        deviation_summaries: List of deviation detail dicts.

    Returns:
        Dictionary with root_cause, corrective_action, preventive_action.
    """
    if not deviation_summaries:
        return dict(_DEFAULT_FALLBACK)

    # Use the type of the first deviation as the primary type
    primary_type = deviation_summaries[0].get("type", "")
    return dict(_FALLBACK_NARRATIVES.get(primary_type, _DEFAULT_FALLBACK))


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

    def generate_capa_narrative(
        self, deviation_summaries: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """Return deterministic CAPA narrative fields for testing.

        Uses the same fallback narratives keyed on deviation type as the
        production fallback, ensuring tests validate realistic content.

        Args:
            deviation_summaries: List of deviation detail dicts.

        Returns:
            Dictionary with root_cause, corrective_action, preventive_action.
        """
        return _capa_narrative_fallback(deviation_summaries)


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
