"""Configuration loader and schema definitions for Site Risk Scoring Engine."""

import json
import os
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, model_validator
from src.backend.config import RISK_WEIGHTS_PATH


EXPECTED_FACTORS = {
    "major_deviation_rate",
    "minor_deviation_rate",
    "deviation_trend",
    "query_resolution_time",
    "enrollment_vs_target",
    "staff_turnover_rate",
    "days_since_last_monitoring_visit",
}


class FactorConfig(BaseModel):
    """Configuration definition for a single site risk factor.

    Attributes:
        name (str): Human-readable factor name.
        weight (float): Multiplier weight (0.0 to 1.0).
        description (str): Explanatory clinical rationale for this factor.
        parameters (dict): Threshold and calibration parameters for factor normalization.
    """
    name: str
    weight: float = Field(ge=0.0, le=1.0)
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)


class RiskConfig(BaseModel):
    """Master configuration for deterministic site risk scoring.

    Attributes:
        version (str): Configuration version string.
        description (str): Overview of the risk scoring methodology.
        factors (dict[str, FactorConfig]): Mapping of factor identifiers to their configs.
    """
    version: str = "1.0"
    description: str = ""
    factors: Dict[str, FactorConfig]

    @model_validator(mode="after")
    def validate_weights_and_factors(self) -> "RiskConfig":
        """Validate that all required 7 factors exist and their weights sum to 1.0 (100%)."""
        factor_keys = set(self.factors.keys())
        missing = EXPECTED_FACTORS - factor_keys
        if missing:
            raise ValueError(f"Missing required risk factor configuration(s): {missing}")

        total_weight = sum(f.weight for f in self.factors.values())
        if abs(total_weight - 1.0) > 1e-4:
            raise ValueError(
                f"Risk factor weights must sum to 1.0 (100%), got {total_weight:.4f}"
            )
        return self


def load_risk_config(config_path: Optional[str] = None) -> RiskConfig:
    """Load, parse, and validate the site risk scoring configuration from JSON.

    Args:
        config_path (Optional[str]): Explicit path to JSON configuration file.
            If None, defaults to `src/backend/config/risk_weights.json`.

    Returns:
        RiskConfig: Validated risk configuration instance.

    Raises:
        FileNotFoundError: If the configuration file cannot be found.
        ValueError: If configuration validation fails (e.g. weights do not sum to 1.0).
    """
    path = config_path or RISK_WEIGHTS_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(f"Site risk configuration file not found at: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return RiskConfig(**data)
