"""
Amar Tax AI Agent - Database & Fallback Module
Treats data/tax_db.json as the Source of Truth with simulated network fallback handling.
"""

import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("AmarTax.Database")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Resolve absolute path to data/tax_db.json
BASE_DIR = Path(__file__).resolve().parent.parent
FALLBACK_DB_PATH = BASE_DIR / "data" / "tax_db.json"

# Simulated remote API URL
REMOTE_API_URL = os.environ.get("NBR_TAX_API_URL", "https://nbr.gov.bd/api/v1/tax_rules_2026.json")


def load_tax_database(source_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Attempts to fetch tax rules from an online API / scraper.
    Falls back gracefully to the Local DB (tax_db.json) upon failure with logging.
    Requirement 7: If web scraping/API fails, fall back to the Local DB (try/except + log message).
    """
    target_url = source_url or REMOTE_API_URL
    logger.info(f"Attempting to query remote tax rules source: {target_url}")

    try:
        req = urllib.request.Request(
            target_url,
            headers={"User-Agent": "AmarTax-AI-Agent/1.0 (NBR Virtual Advisor)"}
        )
        with urllib.request.urlopen(req, timeout=3) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                logger.info("Successfully fetched live tax database from remote source.")
                return data
            else:
                raise urllib.error.HTTPError(
                    target_url, response.status, f"HTTP Error {response.status}", response.headers, None
                )
    except Exception as e:
        logger.warning(
            f"[FALLBACK TRIGGERED] Remote Tax API/Scraping failed: {e}. "
            f"Gracefully falling back to Local Fallback Database at '{FALLBACK_DB_PATH}'."
        )

    # Read from local fallback DB
    if not FALLBACK_DB_PATH.exists():
        raise FileNotFoundError(f"Local Fallback Database not found at {FALLBACK_DB_PATH}")

    with open(FALLBACK_DB_PATH, "r", encoding="utf-8") as f:
        db_data = json.load(f)
        logger.info("Loaded Local Fallback Database successfully as Source of Truth.")
        return db_data


def resolve_taxpayer_category(
    age: int,
    gender: str,
    is_disabled: bool = False,
    is_freedom_fighter: bool = False
) -> Tuple[str, str]:
    """
    Resolves taxpayer category key and display name based on profile.
    Categories:
      - Freedom Fighter: 500,000 BDT
      - Disabled: 475,000 BDT
      - Senior 65+: 400,000 BDT
      - Female: 400,000 BDT
      - General: 350,000 BDT
    """
    if is_freedom_fighter:
        return "freedom_fighter", "Freedom Fighter"
    if is_disabled:
        return "disabled", "Disabled"
    if age >= 65:
        return "senior_65_plus", "Senior 65+"
    if gender.strip().lower() in ["female", "woman", "f"]:
        return "female", "Female"
    return "general", "General"


def get_tax_threshold(category_key: str, db: Optional[Dict[str, Any]] = None) -> float:
    """Returns the tax-free threshold for a given category."""
    database = db or load_tax_database()
    thresholds = database.get("thresholds", {})
    return float(thresholds.get(category_key, thresholds.get("general", 350000)))


def resolve_minimum_tax(location: str, db: Optional[Dict[str, Any]] = None) -> Tuple[float, str]:
    """
    Resolves minimum tax amount and region name based on location string.
    Location rules:
      - Dhaka & Chattogram City Corporation: 5,000 BDT
      - Other City Corporations: 4,000 BDT (e.g., Gazipur, Narayanganj, Rajshahi, Khulna, Sylhet, Barishal, Rangpur, Mymensingh, Cumilla)
      - Rest of country (municipalities, rural): 3,000 BDT
    """
    database = db or load_tax_database()
    min_taxes = database.get("minimum_tax", {})
    loc_clean = location.strip().lower()

    if any(city in loc_clean for city in ["dhaka", "chattogram", "chittagong"]):
        return float(min_taxes.get("dhaka_chattogram_city", 5000)), "Dhaka/Chattogram City Corporation"

    other_city_corps = [
        "gazipur", "narayanganj", "rajshahi", "khulna", "sylhet",
        "barishal", "barisal", "rangpur", "mymensingh", "cumilla", "comilla"
    ]
    if any(city in loc_clean for city in other_city_corps) or "city corporation" in loc_clean:
        return float(min_taxes.get("other_city_corporation", 4000)), "Other City Corporation"

    return float(min_taxes.get("rest_of_country", 3000)), "Rest of the Country"


def calculate_tax_breakdown(
    income: float,
    threshold: float,
    actual_investment: float,
    minimum_tax: float,
    db: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Executes precise slab calculation according to the Local DB rules.
    Simplified Calculation Rules:
      - Taxable Income = Total Income
      - Slabs begin after the tax-free threshold
      - Allowable Investment = min(actual_investment, 20% * income)
      - Rebate = 15% * Allowable Investment
      - Net Tax = max(Gross Tax - Rebate, Minimum Tax) (when income > threshold)
    """
    database = db or load_tax_database()
    slabs = database.get("slabs_after_threshold", [])
    rebate_rules = database.get("investment_rebate", {"rate": 0.15, "max_investment_percent_of_income": 0.20})

    rebate_rate = rebate_rules.get("rate", 0.15)
    max_inv_pct = rebate_rules.get("max_investment_percent_of_income", 0.20)

    # Edge case: Income <= threshold
    if income <= threshold:
        allowable_investment = min(max(0.0, actual_investment), max_inv_pct * max(0.0, income))
        rebate = allowable_investment * rebate_rate
        return {
            "total_income": income,
            "tax_free_threshold": threshold,
            "taxable_after_threshold": 0.0,
            "slab_breakdown": ["Income is within the tax-free threshold; 0% tax applies."],
            "gross_tax": 0.0,
            "allowable_investment": allowable_investment,
            "investment_rebate": 0.0,
            "minimum_tax": minimum_tax,
            "net_payable_tax": 0.0,
            "income_above_threshold": False,
        }

    taxable_amount = income - threshold
    remaining = taxable_amount
    gross_tax = 0.0
    slab_breakdown: List[str] = []

    for slab in slabs:
        limit = slab.get("limit")
        rate = slab.get("rate", 0.0)
        percent = int(rate * 100)

        if limit is None:
            # Final unlimited slab
            if remaining > 0:
                slab_tax = remaining * rate
                gross_tax += slab_tax
                slab_breakdown.append(f"Remaining {remaining:,.0f} BDT @ {percent}% = {slab_tax:,.0f} BDT")
                remaining = 0.0
            break
        else:
            taxable_in_slab = min(remaining, float(limit))
            if taxable_in_slab > 0:
                slab_tax = taxable_in_slab * rate
                gross_tax += slab_tax
                slab_breakdown.append(f"Next {taxable_in_slab:,.0f} BDT @ {percent}% = {slab_tax:,.0f} BDT")
                remaining -= taxable_in_slab
            if remaining <= 0:
                break

    # Allowable investment & rebate
    allowable_investment = min(max(0.0, actual_investment), max_inv_pct * income)
    rebate = allowable_investment * rebate_rate
    tax_after_rebate = max(0.0, gross_tax - rebate)

    # Compare with minimum tax
    net_payable_tax = max(tax_after_rebate, minimum_tax)

    return {
        "total_income": income,
        "tax_free_threshold": threshold,
        "taxable_after_threshold": taxable_amount,
        "slab_breakdown": slab_breakdown,
        "gross_tax": gross_tax,
        "allowable_investment": allowable_investment,
        "investment_rebate": rebate,
        "minimum_tax": minimum_tax,
        "net_payable_tax": net_payable_tax,
        "income_above_threshold": True,
    }


def get_required_documents(
    profession: str,
    income_sources: Optional[List[str]] = None,
    has_tin: bool = True,
    has_investment: bool = False,
    db: Optional[Dict[str, Any]] = None
) -> Tuple[List[str], bool]:
    """
    Generates tailored checklist based on profession, income sources, and TIN status.
    Returns (checklist, is_general_fallback).
    """
    database = db or load_tax_database()
    req_docs = database.get("required_docs", {})
    common_docs = list(req_docs.get("common", ["TIN Certificate", "NID Copy", "Bank Statement"]))

    checklist: List[str] = []

    # Edge Case 5: No TIN -> "TIN Registration" must be added at the top
    if not has_tin:
        checklist.append("TIN Registration")
        # Replace TIN Certificate in common docs if present
        common_docs = [d for d in common_docs if d != "TIN Certificate"]

    prof_clean = profession.strip().lower()
    sources = [s.strip().lower() for s in (income_sources or [])]

    # Map professions and sources to document keys
    doc_keys_found = []
    for key in ["salaried", "business", "freelancer", "landlord", "investor"]:
        if key in prof_clean or any(key in s for s in sources):
            doc_keys_found.append(key)

    # Keyword mappings
    if any(k in prof_clean or any(k in s for s in sources) for k in ["engineer", "officer", "manager", "employee", "teacher", "salary"]):
        if "salaried" not in doc_keys_found:
            doc_keys_found.append("salaried")

    if any(k in prof_clean or any(k in s for s in sources) for k in ["freelance", "contractor", "remote", "remittance"]):
        if "freelancer" not in doc_keys_found:
            doc_keys_found.append("freelancer")

    if any(k in prof_clean or any(k in s for s in sources) for k in ["rent", "landlord", "property", "house owner"]):
        if "landlord" not in doc_keys_found:
            doc_keys_found.append("landlord")

    if has_investment or any(k in prof_clean or any(k in s for s in sources) for k in ["invest", "dps", "sanchaypatra", "shares", "stocks"]):
        if "investor" not in doc_keys_found:
            doc_keys_found.append("investor")

    is_general_fallback = False
    if not doc_keys_found:
        # Edge Case 6: Profession not in DB -> Fall back to general checklist
        is_general_fallback = True
        checklist.extend(common_docs)
    else:
        # Specific order: TIN / Common docs first or custom order
        checklist.extend(common_docs)
        for key in doc_keys_found:
            for item in req_docs.get(key, []):
                if item not in checklist:
                    checklist.append(item)

    # Clean duplicates while preserving order
    deduped = []
    for item in checklist:
        if item not in deduped:
            deduped.append(item)

    return deduped, is_general_fallback

