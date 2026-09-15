"""Hybrid Severity Classifier for ClinGuard AI protocol deviations.

Implements a two-layer severity classification system:
1. Deterministic rules layer — driven by severity_rules.yaml config
2. LLM review layer — optional override for ambiguous cases

The two layers are clearly separated: apply_deterministic_severity() handles
all rule-based logic, while classify_severity() orchestrates the optional
LLM review. A reviewer can see at a glance which severity came from
deterministic logic vs. AI judgment via the severity_source field.
"""

import logging
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import yaml

from src.backend.llm_client import BaseLLMClient

logger = logging.getLogger(__name__)

# Path to the severity rules YAML configuration
_RULES_FILE = os.path.join(os.path.dirname(__file__), "severity_rules.yaml")

# Operator mapping for condition evaluation
_OPERATORS = {
    "gt": lambda val, thresh: val > thresh,
    "gte": lambda val, thresh: val >= thresh,
    "lt": lambda val, thresh: val < thresh,
    "lte": lambda val, thresh: val <= thresh,
    "eq": lambda val, thresh: val == thresh,
}


@lru_cache(maxsize=1)
def load_severity_rules(rules_path: str = _RULES_FILE) -> Dict[str, Any]:
    """Load and cache the severity rules from the YAML configuration file.

    Reads severity_rules.yaml once and caches the result. The YAML file
    defines default severities, conditional overrides, and ambiguity flags
    for each deviation type.

    Args:
        rules_path: Absolute path to the severity_rules.yaml file.
            Defaults to the file co-located with this module.

    Returns:
        Dictionary of severity rules keyed by deviation type.

    Raises:
        FileNotFoundError: If the rules file does not exist.
        yaml.YAMLError: If the YAML is malformed.
    """
    logger.info("Loading severity rules from: %s", rules_path)
    with open(rules_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    rules = config.get("severity_rules", {})
    logger.info("Loaded severity rules for %d deviation types: %s",
                len(rules), list(rules.keys()))
    return rules


def _extract_evidence_value(evidence: Dict[str, Any], field_name: str) -> Optional[float]:
    """Extract a numeric value from the deviation evidence for condition evaluation.

    Searches the evidence.delta dictionary for the specified field. Handles
    both dict-style delta (with named fields) and scalar delta values.

    Args:
        evidence: The deviation's evidence dictionary from the detection engine.
        field_name: The field name to extract (e.g., 'days_outside_window',
            'percentage_deviation').

    Returns:
        The numeric value if found, or None if the field is not present
        or the delta is not a dictionary.
    """
    delta = evidence.get("delta", {})
    if isinstance(delta, dict):
        val = delta.get(field_name)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                return None
    return None


def _evaluate_condition(condition: Dict[str, Any], evidence: Dict[str, Any]) -> bool:
    """Evaluate a single conditional override rule against deviation evidence.

    Extracts the evidence value for the condition's field and applies the
    specified comparison operator against the threshold.

    Args:
        condition: A condition dict from severity_rules.yaml containing
            'field', 'operator', and 'threshold' keys.
        evidence: The deviation's evidence dictionary.

    Returns:
        True if the condition matches, False otherwise.
    """
    field = condition.get("field", "")
    operator = condition.get("operator", "")
    threshold = condition.get("threshold", 0)

    value = _extract_evidence_value(evidence, field)
    if value is None:
        return False

    op_func = _OPERATORS.get(operator)
    if op_func is None:
        logger.warning("Unknown operator '%s' in severity rule condition", operator)
        return False

    return op_func(value, threshold)


def apply_deterministic_severity(
    deviation: Dict[str, Any],
    rules: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str, bool]:
    """Apply the deterministic rules table to assign a default severity.

    Evaluates the deviation type against the severity_rules.yaml configuration.
    Checks conditional overrides in order; the first matching condition wins.
    If no conditions match, the type-level default_severity is used.

    This function contains ONLY deterministic logic — no LLM calls.

    Args:
        deviation: Candidate deviation dictionary from the detection engine,
            containing at minimum 'type' and 'evidence' keys.
        rules: Optional pre-loaded rules dictionary. If None, loads from
            the default YAML file.

    Returns:
        Tuple of (default_severity, rationale_template, is_ambiguous):
            - default_severity (str): 'major', 'minor', or 'administrative'
            - rationale_template (str): Rule-based rationale text
            - is_ambiguous (bool): Whether the case should be sent to LLM review
    """
    if rules is None:
        rules = load_severity_rules()

    dev_type = deviation.get("type", "")
    evidence = deviation.get("evidence", {})

    type_rule = rules.get(dev_type)
    if type_rule is None:
        logger.warning(
            "No severity rule defined for deviation type '%s'. "
            "Defaulting to 'minor'.",
            dev_type,
        )
        return ("minor", "No severity rule configured for this deviation type.", False)

    default_severity = type_rule.get("default_severity", "minor")
    rationale = type_rule.get("rationale_template", "")
    is_ambiguous = type_rule.get("ambiguous", False)

    # Evaluate conditional overrides in order (first match wins)
    conditions: List[Dict[str, Any]] = type_rule.get("conditions", [])
    for condition in conditions:
        if _evaluate_condition(condition, evidence):
            override_severity = condition.get("severity", default_severity)
            override_rationale = condition.get("rationale_template", rationale)
            condition_ambiguous = condition.get("ambiguous", False)

            logger.debug(
                "Condition matched for '%s': field=%s %s %s → severity=%s, ambiguous=%s",
                dev_type,
                condition.get("field"),
                condition.get("operator"),
                condition.get("threshold"),
                override_severity,
                condition_ambiguous,
            )
            return (override_severity, override_rationale, condition_ambiguous)

    return (default_severity, rationale, is_ambiguous)


def classify_severity(
    deviation: Dict[str, Any],
    llm_client: Optional[BaseLLMClient] = None,
) -> Dict[str, Any]:
    """Classify the severity of a deviation using the hybrid rules+LLM approach.

    Orchestrates the two-layer classification:
    1. Applies deterministic rules from severity_rules.yaml to get the default
       severity and determine if the case is ambiguous.
    2. If the case IS ambiguous AND an llm_client is provided, sends the
       deviation to the LLM for review. The LLM may override the severity
       and provides a rationale citing ICH E6(R2).
    3. If the case is NOT ambiguous or no llm_client is available, the
       deterministic severity stands.

    Args:
        deviation: Candidate deviation dictionary from the detection engine.
        llm_client: Optional LLM client for reviewing ambiguous cases.
            Pass None for pure deterministic mode.

    Returns:
        Dictionary with classification results:
            - default_severity (str): The rule-table severity (deterministic)
            - final_severity (str): The post-review severity (may differ if LLM overrides)
            - severity_rationale (str): Human-readable rationale
            - severity_source (str): 'deterministic' or 'llm_override'
    """
    # Layer 1: Deterministic rules
    default_severity, rationale, is_ambiguous = apply_deterministic_severity(deviation)

    result = {
        "default_severity": default_severity,
        "final_severity": default_severity,
        "severity_rationale": rationale,
        "severity_source": "deterministic",
    }

    # Layer 2: LLM review (only for ambiguous cases with an available client)
    if is_ambiguous and llm_client is not None:
        logger.info(
            "Deviation type '%s' flagged as ambiguous — requesting LLM review",
            deviation.get("type", "unknown"),
        )

        llm_context = {
            "type": deviation.get("type", ""),
            "default_severity": default_severity,
            "evidence": deviation.get("evidence", {}),
            "severity_rationale": rationale,
        }

        try:
            llm_result = llm_client.classify_severity(llm_context)
            llm_severity = llm_result.get("severity", "").lower()
            llm_rationale = llm_result.get("rationale", "")

            if llm_severity in ("major", "minor", "administrative"):
                result["final_severity"] = llm_severity
                result["severity_rationale"] = llm_rationale
                result["severity_source"] = "llm_override"

                if llm_severity != default_severity:
                    logger.info(
                        "LLM adjusted severity from '%s' to '%s' for type '%s'",
                        default_severity,
                        llm_severity,
                        deviation.get("type", ""),
                    )
            else:
                logger.warning(
                    "LLM returned invalid severity '%s'; keeping deterministic default",
                    llm_severity,
                )
        except Exception as e:
            logger.error(
                "LLM classification failed: %s. Falling back to deterministic severity.",
                e,
            )

    elif is_ambiguous and llm_client is None:
        logger.debug(
            "Deviation type '%s' is ambiguous but no LLM client available. "
            "Using deterministic default '%s'.",
            deviation.get("type", ""),
            default_severity,
        )

    return result


def classify_batch(
    deviations: List[Dict[str, Any]],
    llm_client: Optional[BaseLLMClient] = None,
) -> List[Dict[str, Any]]:
    """Classify severity for a batch of deviations.

    Convenience wrapper that applies classify_severity to each deviation
    in the list and returns the combined results.

    Args:
        deviations: List of candidate deviation dictionaries.
        llm_client: Optional LLM client for ambiguous case review.

    Returns:
        List of classification result dictionaries, one per input deviation.
    """
    return [classify_severity(dev, llm_client=llm_client) for dev in deviations]
