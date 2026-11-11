"""
Amar Tax AI Agent - Automated Test Suite
Executes all test cases specified in the assignment PDF:
  1. Example Scenario: 34yo Female, Software Engineer, Dhaka, Income 1,500,000 BDT, Investment 200,000 BDT -> Net Tax 110,000 BDT, Status: ✅ Passed
  2. Edge Case 1: 16-year-old, Income 500,000 BDT, Independent Filing -> ⚠️ Minor flag
  3. Edge Case 4: 45-year-old Male, Income 300,000 BDT, Rangpur -> Filing not mandatory with explanatory warning
  4. Edge Case 3: Income 800,000 BDT, Investment 1,000,000 BDT -> ⚠️ Investment > Income flag
  5. Edge Case 5: No TIN -> 'TIN Registration' must be added at top of checklist
  6. Edge Case 6: Profession not in DB -> General checklist fallback
"""

import os
import sys
import json
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src.crew import run_tax_advisor

TEST_CASES = [
    {
        "id": 1,
        "name": "Test Case 1: Example Scenario (Baseline Acceptance)",
        "expected": "Net Tax = 110,000 BDT, ✅ Passed",
        "profile": {
            "age": 34,
            "gender": "Female",
            "profession": "Software Engineer",
            "total_income": 1500000.0,
            "investment": 200000.0,
            "location": "Dhaka",
            "has_tin": True,
            "wants_independent_filing": True,
            "claims_required_to_file": False,
            "income_sources": ["salaried", "freelancer", "investor"],
            "is_disabled": False,
            "is_freedom_fighter": False,
            "raw_prompt": (
                "I am a 34-year-old woman working as a software engineer, and I live in Dhaka. "
                "My annual salary is 1,200,000 BDT and I earn 300,000 BDT from freelancing "
                "(remittance comes through the bank). I have invested 200,000 BDT in DPS and "
                "Sanchaypatra. I have a TIN."
            )
        }
    },
    {
        "id": 2,
        "name": "Test Case 2: Underage Taxpayer (Minor Independent Filing)",
        "expected": "⚠️ Minor flag (Minor cannot file independently)",
        "profile": {
            "age": 16,
            "gender": "Male",
            "profession": "Freelancer",
            "total_income": 500000.0,
            "investment": 0.0,
            "location": "Dhaka",
            "has_tin": True,
            "wants_independent_filing": True,
            "claims_required_to_file": False,
            "income_sources": ["freelancer"],
            "is_disabled": False,
            "is_freedom_fighter": False,
            "raw_prompt": "I am 16 years old earning 500,000 BDT from online freelancing and want to file my taxes independently."
        }
    },
    {
        "id": 3,
        "name": "Test Case 3: Below Tax-Free Threshold in Rangpur",
        "expected": "Filing not mandatory, with an explanatory warning message",
        "profile": {
            "age": 45,
            "gender": "Male",
            "profession": "Teacher",
            "total_income": 300000.0,
            "investment": 0.0,
            "location": "Rangpur",
            "has_tin": True,
            "wants_independent_filing": True,
            "claims_required_to_file": True,
            "income_sources": ["salaried"],
            "is_disabled": False,
            "is_freedom_fighter": False,
            "raw_prompt": "I am a 45-year-old male teacher living in Rangpur earning 300,000 BDT annually. I believe I am required to file."
        }
    },
    {
        "id": 4,
        "name": "Test Case 4: Excessive Investment (Investment > Total Income)",
        "expected": "⚠️ Investment > Income flag",
        "profile": {
            "age": 40,
            "gender": "Male",
            "profession": "Business",
            "total_income": 800000.0,
            "investment": 1000000.0,
            "location": "Chattogram",
            "has_tin": True,
            "wants_independent_filing": True,
            "claims_required_to_file": False,
            "income_sources": ["business", "investor"],
            "is_disabled": False,
            "is_freedom_fighter": False,
            "raw_prompt": "I am a 40-year-old businessman in Chattogram with 800,000 BDT income and 1,000,000 BDT in investments."
        }
    },
    {
        "id": 5,
        "name": "Test Case 5: Missing TIN (Edge Case 5)",
        "expected": "'TIN Registration' must be added at the top of the checklist",
        "profile": {
            "age": 28,
            "gender": "Male",
            "profession": "Software Engineer",
            "total_income": 600000.0,
            "investment": 50000.0,
            "location": "Dhaka",
            "has_tin": False,
            "wants_independent_filing": True,
            "claims_required_to_file": False,
            "income_sources": ["salaried"],
            "is_disabled": False,
            "is_freedom_fighter": False,
            "raw_prompt": "I am 28 years old, earning 600,000 BDT in Dhaka, but I do NOT have a TIN yet."
        }
    },
    {
        "id": 6,
        "name": "Test Case 6: Unlisted Profession Fallback (Edge Case 6)",
        "expected": "Profession not in DB -> Fall back to general checklist",
        "profile": {
            "age": 35,
            "gender": "Male",
            "profession": "Sculptor / Visual Artist",
            "total_income": 450000.0,
            "investment": 0.0,
            "location": "Sylhet",
            "has_tin": True,
            "wants_independent_filing": True,
            "claims_required_to_file": False,
            "income_sources": [],
            "is_disabled": False,
            "is_freedom_fighter": False,
            "raw_prompt": "I am a 35-year-old sculptor living in Sylhet earning 450,000 BDT."
        }
    }
]


def run_all_tests():
    print("\n" + "=" * 90)
    print("           AMAR TAX AI AGENT - COMPREHENSIVE TEST SUITE EXECUTION")
    print("=" * 90)

    results = []

    for tc in TEST_CASES:
        print("\n" + "#" * 90)
        print(f"EXECUTING: {tc['name']}")
        print(f"EXPECTED BEHAVIOR: {tc['expected']}")
        print("#" * 90 + "\n")

        try:
            report_output = run_tax_advisor(tc["profile"])
            print("\n--- REPORT OUTPUT ---")
            print(report_output)
            results.append({
                "id": tc["id"],
                "name": tc["name"],
                "expected": tc["expected"],
                "status": "COMPLETED",
                "output": report_output
            })
        except Exception as e:
            print(f"ERROR executing {tc['name']}: {e}")
            results.append({
                "id": tc["id"],
                "name": tc["name"],
                "expected": tc["expected"],
                "status": f"FAILED: {e}",
                "output": ""
            })

    # Summary
    print("\n" + "=" * 90)
    print("                       ALL TEST CASES EXECUTION SUMMARY")
    print("=" * 90)
    for r in results:
        print(f"[{r['status']}] {r['name']} -> Expected: {r['expected']}")

    # Save to disk for review
    out_file = BASE_DIR / "test_results_summary.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nSaved full results to: {out_file}")


if __name__ == "__main__":
    run_all_tests()

