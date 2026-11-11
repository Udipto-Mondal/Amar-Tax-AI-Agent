"""
Amar Tax AI Agent - Crew Orchestration Module
Assembles the 4-agent CrewAI pipeline with sequential execution and verbose logging.
"""

import asyncio
import concurrent.futures
import logging
from typing import Any, Dict
from crewai import Crew, Process

from src.agents import (
    create_calculator_agent,
    create_classifier_agent,
    create_organizer_agent,
    create_reviewer_agent
)
from src.config import get_llm
from src.tasks import (
    create_calculation_task,
    create_classification_task,
    create_documentation_task,
    create_review_task
)

logger = logging.getLogger("AmarTax.Crew")


def build_tax_crew(profile: Dict[str, Any], llm=None) -> Crew:
    """
    Builds and configures the Amar Tax CrewAI system for a given user profile.
    Orchestration Pattern:
      User Profile -> Classifier -> Calculator -> Organizer -> Reviewer
    """
    active_llm = llm or get_llm()

    # 1. Instantiate the 4 specialized agents
    classifier = create_classifier_agent(llm=active_llm)
    calculator = create_calculator_agent(llm=active_llm)
    organizer = create_organizer_agent(llm=active_llm)
    reviewer = create_reviewer_agent(llm=active_llm)

    # 2. Instantiate tasks with sequential context passing
    task1_classify = create_classification_task(agent=classifier, profile=profile)
    task2_calculate = create_calculation_task(agent=calculator, profile=profile, context_tasks=[task1_classify])
    task3_document = create_documentation_task(agent=organizer, profile=profile, context_tasks=[task1_classify])
    task4_review = create_review_task(
        agent=reviewer,
        profile=profile,
        context_tasks=[task1_classify, task2_calculate, task3_document]
    )

    # 3. Assemble crew with verbose=True
    crew = Crew(
        agents=[classifier, calculator, organizer, reviewer],
        tasks=[task1_classify, task2_calculate, task3_document, task4_review],
        process=Process.sequential,
        verbose=True
    )

    return crew


def _kickoff_sync_safe(crew: Crew):
    """Run crew.kickoff() safely even when called inside an active asyncio event loop (e.g., Jupyter/Colab)."""
    try:
        asyncio.get_running_loop()
        in_loop = True
    except RuntimeError:
        in_loop = False

    if in_loop:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(crew.kickoff).result()
    return crew.kickoff()


def run_tax_advisor(profile: Dict[str, Any], llm=None) -> str:
    """
    Executes the Amar Tax advisory crew on a taxpayer profile.
    Returns the string output of the final Tax Readiness Report.
    """
    logger.info(f"Initiating Amar Tax Advisor for: {profile.get('profession', 'Individual')} "
                f"({profile.get('age')}y, {profile.get('gender')}, {profile.get('location')})")

    crew = build_tax_crew(profile=profile, llm=llm)
    result = _kickoff_sync_safe(crew)

    return str(result)

