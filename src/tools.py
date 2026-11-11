"""
Amar Tax AI Agent - Custom Tools Module
Builds custom tools (@tool) for CrewAI agents to interact with the tax database,
calculate taxes strictly by slab, assemble document checklists, and validate compliance edge cases.
"""

import json
from typing import Optional
from crewai.tools import tool

from src.database import (
    calculate_tax_breakdown,
    get_required_documents,
    get_tax_threshold,
    load_tax_database,
    resolve_minimum_tax,
    resolve_taxpayer_category,
)


@tool("lookup_tax_db")
def lookup_tax_db(query_type: str, category: str = "", location: str = "") -> str:
    """
    Look up tax rules, thresholds, minimum taxes, slabs, and rebate parameters from the tax database.
    Demonstrates network fallback mechanism (try remote API/scraper, except fall back to local DB).

    Args:
        query_type: One of 'thresholds', 'minimum_tax', 'slabs', 'rebate_rules', 'all'
        category: Optional category name ('female', 'general', 'senior_65_plus', 'disabled', 'freedom_fighter')
        location: Optional taxpayer location ('Dhaka', 'Chattogram', 'Rangpur', etc.)
    """
    db = load_tax_database()
    query = query_type.strip().lower()

    if query == "thresholds":
        if category:
            cat_key = category.strip().lower().replace(" ", "_")
            threshold = get_tax_threshold(cat_key, db)
            return json.dumps({
                "category": category,
                "category_key": cat_key,
                "tax_free_threshold_bdt": threshold,
                "tax_year": db.get("tax_year", "2026-27")
            }, indent=2)
        return json.dumps({
            "tax_year": db.get("tax_year", "2026-27"),
            "filing_deadline": db.get("filing_deadline", "2026-11-30"),
            "thresholds": db.get("thresholds", {})
        }, indent=2)

    if query == "minimum_tax":
        min_tax, tier = resolve_minimum_tax(location, db)
        return json.dumps({
            "location_provided": location,
            "matched_tier": tier,
            "minimum_tax_bdt": min_tax,
            "all_minimum_taxes": db.get("minimum_tax", {})
        }, indent=2)

    if query == "slabs":
        return json.dumps({
            "slabs_after_threshold": db.get("slabs_after_threshold", [])
        }, indent=2)

    if query == "rebate_rules":
        return json.dumps({
            "investment_rebate": db.get("investment_rebate", {})
        }, indent=2)

    # Return full database summary
    return json.dumps(db, indent=2)


@tool("calculate_slab_tax")
def calculate_slab_tax(
    income: float,
    threshold: float,
    investment: float,
    minimum_tax: float
) -> str:
    """
    Accurately calculates slab tax, investment rebate, and net payable tax
    strictly according to the Local Fallback Database rules. Never invents rates.

    Args:
        income: Total annual taxable income in BDT.
        threshold: Tax-free threshold in BDT for taxpayer's category.
        investment: Total eligible investment amount in BDT.
        minimum_tax: Location-based minimum tax in BDT.
    """
    db = load_tax_database()
    res = calculate_tax_breakdown(
        income=float(income),
        threshold=float(threshold),
        actual_investment=float(investment),
        minimum_tax=float(minimum_tax),
        db=db
    )
    return json.dumps(res, indent=2)


@tool("get_document_checklist")
def get_document_checklist(
    profession: str,
    income_sources_csv: str = "",
    has_tin: bool = True,
    has_investment: bool = False
) -> str:
    """
    Generates customized document checklist based on profession, income sources, and TIN status.
    Handles edge cases:
      - If no TIN: adds 'TIN Registration' at the top of the checklist.
      - If profession not in DB: gracefully falls back to the general checklist.

    Args:
        profession: Taxpayer profession (e.g., 'Software Engineer', 'Doctor', 'Salaried')
        income_sources_csv: Comma-separated income sources (e.g., 'salary, freelancing')
        has_tin: Boolean indicating whether taxpayer already possesses a TIN
        has_investment: Boolean indicating whether taxpayer has investments to claim rebate
    """
    db = load_tax_database()
    sources = [s.strip() for s in income_sources_csv.split(",") if s.strip()]
    checklist, is_fallback = get_required_documents(
        profession=profession,
        income_sources=sources,
        has_tin=has_tin,
        has_investment=has_investment,
        db=db
    )

    result = {
        "profession": profession,
        "income_sources": sources,
        "has_tin": has_tin,
        "is_general_fallback": is_fallback,
        "documents_needed": checklist,
        "notes": (
            "Profession not recognized in DB; applied general fallback checklist."
            if is_fallback else "Customized checklist based on declared profession and sources."
        )
    }
    return json.dumps(result, indent=2)


@tool("validate_compliance_and_edge_cases")
def validate_compliance_and_edge_cases(
    age: int,
    income: float,
    investment: float,
    threshold: float,
    claims_required_to_file: bool = False,
    has_tin: bool = True,
    wants_independent_filing: bool = True,
    profession_is_fallback: bool = False
) -> str:
    """
    Cross-checks outputs and catches all required assignment edge cases:
      1. Age < 18 and file independently -> ⚠️ Minor cannot file independently
      2. Negative or impossible income -> Flag as invalid input
      3. Investment > total income -> ⚠️ Investment exceeds income, please verify
      4. Income below threshold but claims 'required to file' -> Inform filing not mandatory (check Minimum Tax)
      5. No TIN -> 'TIN Registration' must be added at top of checklist
      6. Profession not in DB -> Fall back to general checklist

    Returns compliance audit status ('✅ Passed' or '⚠️ Flagged') and list of flags.
    """
    flags = []

    # Edge Case 1: Minor independent filing
    if age < 18 and wants_independent_filing:
        flags.append("⚠️ Minor cannot file independently")

    # Edge Case 2: Negative or impossible income
    if income < 0:
        flags.append("⚠️ Flag as invalid input: Income cannot be negative")

    # Edge Case 3: Investment exceeds income
    if investment > income and income > 0:
        flags.append("⚠️ Investment exceeds income, please verify")

    # Edge Case 4: Income below threshold but claims required to file
    if income <= threshold and claims_required_to_file:
        flags.append(
            f"⚠️ Inform them that filing is not mandatory (income {income:,.0f} BDT is within "
            f"the tax-free threshold of {threshold:,.0f} BDT, but check the Minimum Tax rule)"
        )

    # Edge Case 5: No TIN
    if not has_tin:
        flags.append("⚠️ No TIN: 'TIN Registration' must be added at the top of the checklist")

    # Edge Case 6: Profession not in DB
    if profession_is_fallback:
        flags.append("⚠️ Profession not in DB: Fall back to the general checklist")

    status = "⚠️ Flagged" if flags else "✅ Passed"

    return json.dumps({
        "compliance_status": status,
        "total_flags": len(flags),
        "flags": flags
    }, indent=2)

