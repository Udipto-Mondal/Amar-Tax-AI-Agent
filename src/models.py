"""
Amar Tax AI Agent - Pydantic Data Models
Defines structured input profiles and task output schemas for CrewAI.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    """User input profile provided to the Amar Tax system."""
    raw_prompt: Optional[str] = Field(None, description="Original user text input if available")
    age: int = Field(..., description="Age of the taxpayer in years")
    gender: str = Field(..., description="Gender: Female, Male, or Other")
    profession: str = Field(..., description="Taxpayer profession, e.g. software engineer, doctor")
    total_income: float = Field(..., description="Annual total income in BDT")
    investment: float = Field(0.0, description="Annual investment eligible for tax rebate in BDT")
    location: str = Field(..., description="Location of residence, e.g. Dhaka, Rangpur")
    has_tin: bool = Field(True, description="Whether the taxpayer already has an active TIN")
    wants_independent_filing: bool = Field(True, description="Whether the taxpayer intends to file independently")
    claims_required_to_file: bool = Field(False, description="Whether user explicitly claims mandatory filing")
    income_sources: List[str] = Field(default_factory=list, description="List of income sources (salary, freelance, etc.)")
    is_disabled: bool = Field(False, description="Whether the taxpayer is a person with disability")
    is_freedom_fighter: bool = Field(False, description="Whether the taxpayer is a Gazetted War-Wounded Freedom Fighter")


class TaxpayerEligibilityOutput(BaseModel):
    """Structured output from Agent 1 (Classifier / Senior Taxpayer Classification Officer)."""
    taxpayer_category: str = Field(..., description="Category: Female, General, Senior 65+, Disabled, Freedom Fighter")
    is_mandatory: bool = Field(..., description="Whether filing an income tax return is mandatory")
    tax_free_threshold: float = Field(..., description="Tax-free threshold amount in BDT")
    minimum_tax: float = Field(..., description="Minimum tax payable based on location in BDT")
    location_tier: str = Field(..., description="Classification of taxpayer's location")
    eligibility_notes: str = Field(..., description="Explanation of mandatory filing rule and age restrictions")
    flags: List[str] = Field(default_factory=list, description="Any detected edge case warnings or flags")


class TaxCalculationOutput(BaseModel):
    """Structured output from Agent 2 (Slab Calculator / Chartered Tax Accountant)."""
    total_income: float = Field(..., description="Total annual income in BDT")
    tax_free_threshold: float = Field(..., description="Applicable tax-free threshold in BDT")
    taxable_income_after_threshold: float = Field(..., description="Income amount subject to tax slabs in BDT")
    gross_tax: float = Field(..., description="Gross tax before rebate in BDT")
    slab_breakdown: List[str] = Field(default_factory=list, description="Step-by-step breakdown across tax slabs")
    allowable_investment: float = Field(..., description="Allowable investment amount (capped at 20% of income)")
    investment_rebate: float = Field(..., description="Investment rebate amount (15% of allowable investment)")
    minimum_tax: float = Field(..., description="Minimum applicable tax for taxpayer's location")
    net_payable_tax: float = Field(..., description="Net tax payable after rebate comparison against minimum tax")
    calculation_summary: str = Field(..., description="Summary of computation logic and constraints")
    flags: List[str] = Field(default_factory=list, description="Any computational flags")


class DocumentChecklistOutput(BaseModel):
    """Structured output from Agent 3 (Document Organizer / Return Filing Documentation Officer)."""
    profession: str = Field(..., description="Taxpayer profession considered")
    has_tin: bool = Field(..., description="Whether the taxpayer has a TIN")
    documents_needed: List[str] = Field(default_factory=list, description="List of required documents and proofs")
    is_fallback_checklist: bool = Field(False, description="True if profession was not in DB and general list was used")
    notes: str = Field("", description="Additional filing tips or guidelines")


class TaxReadinessReport(BaseModel):
    """Final structured output from Agent 4 (Compliance Reviewer / Validator Agent)."""
    taxpayer_category: str = Field(..., description="Taxpayer category, e.g. Female, General")
    total_income: float = Field(..., description="Total annual income in BDT")
    tax_free_threshold: float = Field(..., description="Tax-free threshold in BDT")
    gross_tax: float = Field(..., description="Gross slab-based tax in BDT")
    investment_rebate: float = Field(..., description="Investment rebate in BDT")
    minimum_tax: float = Field(..., description="Location minimum tax in BDT")
    net_payable_tax: float = Field(..., description="Net payable tax in BDT")
    documents_needed: List[str] = Field(default_factory=list, description="All required documents")
    compliance_status: str = Field(..., description="Final audit status: '✅ Passed' or '⚠️ Flagged'")
    identified_issues: List[str] = Field(default_factory=list, description="All caught errors, flags, or edge cases")
    markdown_table: str = Field(..., description="English Markdown Table formatted strictly as required")
    bangla_summary: str = Field(..., description="3-4 line Bangla summary of the tax readiness report")
