"""
Amar Tax AI Agent - Tasks Definition Module
Defines the 4 sequential tasks with context passing and structured Pydantic outputs.
Pattern: Classifier -> Calculator -> Organizer -> Reviewer
"""

from typing import Any, Dict, List
from crewai import Agent, Task

from src.models import (
    DocumentChecklistOutput,
    TaxCalculationOutput,
    TaxpayerEligibilityOutput,
    TaxReadinessReport
)


def create_classification_task(
    agent: Agent,
    profile: Dict[str, Any]
) -> Task:
    """
    Task 1: Taxpayer Eligibility & Classification
    Uses Agent 1 to classify category, threshold, and minimum tax.
    Outputs structured TaxpayerEligibilityOutput.
    """
    description = (
        f"Analyze the following taxpayer profile:\n"
        f"  - Age: {profile.get('age')}\n"
        f"  - Gender: {profile.get('gender')}\n"
        f"  - Profession: {profile.get('profession')}\n"
        f"  - Total Annual Income: {profile.get('total_income', 0):,} BDT\n"
        f"  - Investment: {profile.get('investment', 0):,} BDT\n"
        f"  - Location: {profile.get('location')}\n"
        f"  - Has TIN: {profile.get('has_tin', True)}\n"
        f"  - Claims Required to File: {profile.get('claims_required_to_file', False)}\n"
        f"  - Wants Independent Filing: {profile.get('wants_independent_filing', True)}\n"
        f"  - Disabled: {profile.get('is_disabled', False)}\n"
        f"  - Freedom Fighter: {profile.get('is_freedom_fighter', False)}\n\n"
        f"Instructions:\n"
        f"1. Use `lookup_tax_db` to determine the taxpayer category (General, Female, Senior 65+, Disabled, Freedom Fighter) "
        f"   and its corresponding tax-free threshold.\n"
        f"2. Determine the location-based minimum tax (Dhaka/Chattogram City: 5,000 BDT, Other City Corp: 4,000 BDT, Rest: 3,000 BDT).\n"
        f"3. Check whether return filing is mandatory.\n"
        f"4. CRITICAL RULE: If the taxpayer is under 18 years old and wants to file independently, you MUST flag:\n"
        f"   '⚠️ Minor cannot file independently'.\n"
        f"5. If income is below the tax-free threshold, note that filing is not mandatory (unless claiming or holding specific assets)."
    )

    expected_output = (
        "A structured TaxpayerEligibilityOutput containing taxpayer_category, is_mandatory, "
        "tax_free_threshold, minimum_tax, location_tier, eligibility_notes, and any flags."
    )

    return Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
        output_pydantic=TaxpayerEligibilityOutput
    )


def create_calculation_task(
    agent: Agent,
    profile: Dict[str, Any],
    context_tasks: List[Task]
) -> Task:
    """
    Task 2: Slab Tax Computation
    Uses Agent 2 with context from Task 1.
    Outputs structured TaxCalculationOutput.
    """
    description = (
        f"Using the classification details from the Senior Taxpayer Classification Officer as context, "
        f"compute the complete tax obligation for the taxpayer with total income {profile.get('total_income', 0):,} BDT "
        f"and investment {profile.get('investment', 0):,} BDT.\n\n"
        f"Instructions:\n"
        f"1. Use `calculate_slab_tax` and `lookup_tax_db` tools to compute the figures strictly according to Local DB rules.\n"
        f"2. Slabs begin after the tax-free threshold determined in Task 1.\n"
        f"3. Slabs after threshold:\n"
        f"   - First 100,000 BDT @ 5%\n"
        f"   - Next 400,000 BDT @ 10%\n"
        f"   - Next 500,000 BDT @ 15%\n"
        f"   - Next 500,000 BDT @ 20%\n"
        f"   - Remaining @ 25%\n"
        f"4. Allowable Investment = min(actual_investment, 20% * income).\n"
        f"5. Investment Rebate = 15% * Allowable Investment.\n"
        f"6. Net Tax = max(Gross Tax - Rebate, Minimum Tax) when income is above the threshold.\n"
        f"   If income is below the threshold, gross tax is 0 and net payable tax is 0.\n"
        f"7. Check computational edge cases:\n"
        f"   - Negative income -> flag as invalid input.\n"
        f"   - Investment > income -> flag '⚠️ Investment exceeds income, please verify'.\n"
        f"8. Provide exact numeric values and step-by-step slab breakdown."
    )

    expected_output = (
        "A structured TaxCalculationOutput containing total_income, tax_free_threshold, "
        "taxable_income_after_threshold, gross_tax, slab_breakdown, allowable_investment, "
        "investment_rebate, minimum_tax, net_payable_tax, calculation_summary, and flags."
    )

    return Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
        context=context_tasks,
        output_pydantic=TaxCalculationOutput
    )


def create_documentation_task(
    agent: Agent,
    profile: Dict[str, Any],
    context_tasks: List[Task]
) -> Task:
    """
    Task 3: Document Checklist Preparation
    Uses Agent 3 with context from Task 1.
    Outputs structured DocumentChecklistOutput.
    """
    sources_str = ", ".join(profile.get("income_sources", []))
    description = (
        f"Generate the comprehensive document checklist for this taxpayer:\n"
        f"  - Profession: {profile.get('profession')}\n"
        f"  - Income Sources: {sources_str}\n"
        f"  - Has TIN: {profile.get('has_tin', True)}\n"
        f"  - Total Investment: {profile.get('investment', 0):,} BDT\n\n"
        f"Instructions:\n"
        f"1. Use `get_document_checklist` to query the required documents.\n"
        f"2. CRITICAL RULE: If the user does not have a TIN (has_tin=False), 'TIN Registration' MUST be "
        f"   added at the top of the checklist.\n"
        f"3. If the profession is not in the database and no specific sources match, fall back to the "
        f"   general checklist.\n"
        f"4. If taxpayer has investments (DPS, Sanchaypatra, etc.), include investment proof certificates.\n"
        f"5. Include salary certificate for salaried employees, remittance proof for freelancers, etc."
    )

    expected_output = (
        "A structured DocumentChecklistOutput with profession, has_tin, documents_needed, "
        "is_fallback_checklist, and notes."
    )

    return Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
        context=context_tasks,
        output_pydantic=DocumentChecklistOutput
    )


def create_review_task(
    agent: Agent,
    profile: Dict[str, Any],
    context_tasks: List[Task]
) -> Task:
    """
    Task 4: Compliance Review & Tax Readiness Report
    Uses Agent 4 with context from Tasks 1, 2, and 3.
    Produces final English Markdown Table + 3-4 line Bangla summary.
    """
    description = (
        f"Audit and cross-check the complete findings from the Senior Taxpayer Classification Officer, "
        f"Chartered Tax Accountant, and Return Filing Documentation Officer.\n\n"
        f"User Profile Summary:\n"
        f"  - Age: {profile.get('age')}\n"
        f"  - Gender: {profile.get('gender')}\n"
        f"  - Profession: {profile.get('profession')}\n"
        f"  - Income: {profile.get('total_income', 0):,} BDT\n"
        f"  - Investment: {profile.get('investment', 0):,} BDT\n"
        f"  - Location: {profile.get('location')}\n"
        f"  - Has TIN: {profile.get('has_tin', True)}\n"
        f"  - Claims Required to File: {profile.get('claims_required_to_file', False)}\n"
        f"  - Wants Independent Filing: {profile.get('wants_independent_filing', True)}\n\n"
        f"Instructions:\n"
        f"1. Use `validate_compliance_and_edge_cases` to verify all 6 edge cases:\n"
        f"   - Age < 18 and file independently -> '⚠️ Minor cannot file independently'\n"
        f"   - Negative or impossible income -> 'Flag as invalid input'\n"
        f"   - Investment > total income -> '⚠️ Investment exceeds income, please verify'\n"
        f"   - Income below tax-free threshold but claims 'required to file' -> "
        f"     'Inform them that filing is not mandatory (but check the Minimum Tax rule)'\n"
        f"   - No TIN -> 'TIN Registration' must be at top of checklist\n"
        f"   - Profession not in DB -> Fall back to general checklist\n"
        f"2. Assign final compliance status: '✅ Passed' if no fatal compliance flags exist, else '⚠️ Flagged'.\n"
        f"3. Generate the Final Tax Readiness Report containing:\n"
        f"   A) English Markdown Table with the exact fields:\n"
        f"      | Field | Result |\n"
        f"      | :--- | :--- |\n"
        f"      | Taxpayer Category | <Category> |\n"
        f"      | Total Income | <Income> BDT |\n"
        f"      | Tax-free Threshold | <Threshold> BDT |\n"
        f"      | Gross Tax (Slab-based) | <Gross Tax> BDT |\n"
        f"      | Investment Rebate (15%) | <Rebate> BDT |\n"
        f"      | Minimum Tax (<Location>) | <Min Tax> BDT |\n"
        f"      | Net Payable Tax | <Net Tax> BDT |\n"
        f"      | Documents Needed | <Comma-separated list> |\n"
        f"      | Compliance Status | ✅ Passed / ⚠️ Flagged |\n\n"
        f"   B) Warning / Flag Section (if any flags are raised).\n"
        f"   C) Bangla Summary (strictly 3 to 4 lines explaining total income, tax-free threshold, "
        f"      net payable tax, and filing advice in clear, natural Bengali)."
    )

    expected_output = (
        "The complete Tax Readiness Report containing the English Markdown Table, "
        "any compliance edge case flags, and the 3-4 line Bangla summary."
    )

    return Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
        context=context_tasks
    )
