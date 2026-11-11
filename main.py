"""
Amar Tax AI Agent - Main Application Entrypoint
Provides an interactive command-line interface and test runner for virtual tax advisory.
"""

import sys
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src.crew import run_tax_advisor
from test_cases import TEST_CASES, run_all_tests


def get_custom_profile():
    """Interactively prompts the user for their profile details."""
    print("\n" + "=" * 60)
    print("      ENTER TAXPAYER PROFILE FOR VIRTUAL ADVISORY")
    print("=" * 60)

    try:
        age_str = input("Enter Age (e.g., 34): ").strip()
        age = int(age_str) if age_str else 30

        gender = input("Enter Gender [Male/Female/Other] (default: General): ").strip() or "General"
        profession = input("Enter Profession (e.g., Software Engineer, Doctor, Business): ").strip() or "General"

        inc_str = input("Enter Total Annual Income in BDT (e.g., 1500000): ").strip()
        total_income = float(inc_str) if inc_str else 0.0

        inv_str = input("Enter Total Investment in BDT (e.g., 200000): ").strip()
        investment = float(inv_str) if inv_str else 0.0

        location = input("Enter City/Location (e.g., Dhaka, Chattogram, Rangpur): ").strip() or "Dhaka"

        tin_str = input("Do you already have a TIN? [y/n] (default: y): ").strip().lower()
        has_tin = False if tin_str in ["n", "no", "false"] else True

        req_str = input("Do you claim filing is mandatory? [y/n] (default: n): ").strip().lower()
        claims_required_to_file = True if req_str in ["y", "yes", "true"] else False

        dis_str = input("Are you a Person with Disability? [y/n] (default: n): ").strip().lower()
        is_disabled = True if dis_str in ["y", "yes", "true"] else False

        ff_str = input("Are you a Gazetted War-Wounded Freedom Fighter? [y/n] (default: n): ").strip().lower()
        is_freedom_fighter = True if ff_str in ["y", "yes", "true"] else False

        sources_raw = input("Enter Income Sources separated by comma (e.g. salary, freelancing, rent): ").strip()
        income_sources = [s.strip().lower() for s in sources_raw.split(",") if s.strip()]

        return {
            "age": age,
            "gender": gender,
            "profession": profession,
            "total_income": total_income,
            "investment": investment,
            "location": location,
            "has_tin": has_tin,
            "wants_independent_filing": True,
            "claims_required_to_file": claims_required_to_file,
            "income_sources": income_sources,
            "is_disabled": is_disabled,
            "is_freedom_fighter": is_freedom_fighter,
            "raw_prompt": f"{age}yo {gender} {profession} in {location} with income {total_income:,.0f} BDT"
        }
    except Exception as e:
        print(f"Invalid input: {e}. Falling back to default example profile.")
        return TEST_CASES[0]["profile"]


def main():
    print("=" * 70)
    print("       'AMAR TAX' AI AGENT - MULTI-AGENT VIRTUAL TAX ADVISOR")
    print("      Pattern: Profile -> Specialized Agents -> Markdown + Bangla")
    print("=" * 70)
    print("\nSelect an option to execute:")
    print("  1. Run Example Scenario (34yo Female Software Engineer, Dhaka - 1,500,000 BDT)")
    print("  2. Run Test Case 2: Underage Taxpayer (16yo, 500,000 BDT) -> ⚠️ Minor flag")
    print("  3. Run Test Case 3: Below Threshold (45yo Male, Rangpur - 300,000 BDT)")
    print("  4. Run Test Case 4: Excessive Investment (800k Income vs 1M Investment)")
    print("  5. Run Test Case 5: Missing TIN (No TIN -> TIN Registration at top)")
    print("  6. Run Test Case 6: Unlisted Profession (Fallback general checklist)")
    print("  7. Run ALL Test Cases sequentially")
    print("  8. Enter Custom Taxpayer Profile interactively")
    print("  0. Exit")

    choice = input("\nEnter your choice (0-8) [default: 1]: ").strip() or "1"

    if choice == "0":
        print("Exiting Amar Tax. Have a compliant tax year!")
        return
    elif choice in ["1", "2", "3", "4", "5", "6"]:
        idx = int(choice) - 1
        tc = TEST_CASES[idx]
        print(f"\n---> Launching {tc['name']}...")
        report = run_tax_advisor(tc["profile"])
        print("\n" + "=" * 70)
        print("FINAL REPORT:")
        print("=" * 70)
        print(report)
    elif choice == "7":
        run_all_tests()
    elif choice == "8":
        profile = get_custom_profile()
        print("\n---> Running Amar Tax Multi-Agent Advisory Crew...")
        report = run_tax_advisor(profile)
        print("\n" + "=" * 70)
        print("FINAL REPORT:")
        print("=" * 70)
        print(report)
    else:
        print(f"Unknown choice '{choice}'. Running default Example Scenario...")
        report = run_tax_advisor(TEST_CASES[0]["profile"])
        print("\n" + "=" * 70)
        print("FINAL REPORT:")
        print("=" * 70)
        print(report)


if __name__ == "__main__":
    main()

