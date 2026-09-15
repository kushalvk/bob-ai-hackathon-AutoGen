"""Drug synonym lookup dictionary and normalization utilities.

Note: In a production deployment, this static mapping would be replaced or augmented
by a full clinical drug ontology service (such as RxNorm, ChEMBL, or UMLS Concept Unique Identifiers).
"""

import re
from typing import Dict, List, Set, Optional

# Static mapping of canonical prohibited drug names to brand names, generic variants, and synonyms
DRUG_SYNONYM_MAPPING: Dict[str, List[str]] = {
    "ketoconazole": [
        "nizoral",
        "fungoral",
        "extina",
        "ketoderm",
        "ketoconazole 200mg",
        "ketoconazole tab",
    ],
    "clarithromycin": [
        "biaxin",
        "klaricid",
        "klacid",
        "clarithromycin 500mg",
        "clarithromycin xl",
    ],
    "st. john's wort": [
        "st. johns wort",
        "st johns wort",
        "st john's wort",
        "hypericum perforatum",
        "hypericum",
        "johns wort",
    ],
    "rifampin": [
        "rifadin",
        "rimactane",
        "rifampicin",
        "rifampin 300mg",
    ],
}


def normalize_drug_name(raw_name: str) -> str:
    """Normalize a drug string by lowercasing, stripping dosage numbers/units, and trimming whitespace.

    Args:
        raw_name (str): Raw drug name from concomitant meds log or protocol.

    Returns:
        str: Cleaned and normalized drug string.
    """
    if not raw_name:
        return ""
    
    lowered = raw_name.lower().strip()
    # Replace punctuation except apostrophe
    cleaned = re.sub(r"[^\w\s\']", "", lowered)
    return cleaned


def is_prohibited_comedication(comed_name: str, prohibited_list: List[str]) -> tuple[bool, Optional[str]]:
    """Determine if a concomitant medication matches any entry in a prohibited medications list.

    Evaluates case-insensitive exact matches, substring containment, and synonym aliases.

    Args:
        comed_name (str): Concomitant medication reported in visit record.
        prohibited_list (List[str]): List of prohibited drug names from protocol.

    Returns:
        tuple[bool, Optional[str]]: (is_prohibited, matched_prohibited_canonical_name)
    """
    normalized_comed = normalize_drug_name(comed_name)
    if not normalized_comed:
        return False, None

    for prohibited in prohibited_list:
        normalized_prohibited = normalize_drug_name(prohibited)
        canonical_key = prohibited.lower().strip()

        # 1. Direct case-insensitive / substring match
        if normalized_prohibited in normalized_comed or normalized_comed in normalized_prohibited:
            return True, prohibited

        # 2. Check synonym dictionary
        synonyms = DRUG_SYNONYM_MAPPING.get(canonical_key, [])
        for syn in synonyms:
            normalized_syn = normalize_drug_name(syn)
            if normalized_syn in normalized_comed or normalized_comed in normalized_syn:
                return True, prohibited

    return False, None
