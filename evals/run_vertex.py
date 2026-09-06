#!/usr/bin/env python3
"""PHASE_09.md §9.2: Vertex AI Evaluation (Gen AI evaluation service) rubric-based
metrics -- RiskAssessor rationale quality (coherence, groundedness) and AskOuroboros
answer quality + a deterministic citation-correctness check.

Needs the `google-cloud-aiplatform[evaluation]` extra (pandas/tqdm), deliberately not
a project dependency (same reasoning as `google-adk[eval]` -- evals/adk/README.md):

    uv run --with "google-cloud-aiplatform[evaluation]" python evals/run_vertex.py

RiskAssessor: runs the real `risk_assessor_agent` (ADK `InMemoryRunner`, not a
reimplementation) against real golden-set legal claims already carrying real Evidence
(evals/run_golden.py's own fixtures) to produce real `Risk.rationale` text, scored on
Vertex's built-in `coherence`/`groundedness` rubrics.

AskOuroboros: runs real live questions through the already-deployed Agent Engine
(`services.dashboard_api.runs.ask_question`, the same function `dashboard_api`'s
`/projects/{id}/ask` endpoint calls -- Phase 8.4), scored on `question_answering_quality`
plus a deterministic check that every `[n]` marker in the answer maps to a real,
listed citation (a structural property better verified in code than by an LLM judge).
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from google.adk.runners import InMemoryRunner
from google.genai import types
from vertexai.evaluation import EvalTask, MetricPromptTemplateExamples

from agents.ouroboros.clear.risk_assessor import risk_assessor_agent
from evals.run_golden import _seed_legal_project
from packages.ledger.db import session_scope
from packages.ledger.repositories import ClaimRepo, EvidenceRepo, RiskRepo
from services.dashboard_api.runs import ask_question

_RESULTS_DIR = Path(__file__).parent / "results"
_RISK_ASSESSOR_APP = "ouroboros"
_RISK_CLAIM_COUNT = 10  # a modest, real subset of the 25 golden legal claims

_ASK_QUESTIONS = [
    "Is there an existing claim about the Coca-Cola product placement in this project?",
    "Can we show a Pepsi sign in the Mumbai scene?",
    "What did we decide about Beatles music rights last time?",
    "What's our studio policy on depicting real living persons?",
    "Is Coca-Cola still an actively registered trademark?",
    "What did we decide about Bohemian Rhapsody last year?",
    "Is there a claim about a Nike logo in this project?",
    "What's the risk level of the Amul billboard claim?",
    "Have we cleared any Apple product placements before?",
    "What did we decide about the moon landing viewership claim?",
    "Is there precedent for showing a real politician's photo in a documentary?",
    "What's our policy on using a real company's trademark in a negative context?",
    "Has this studio ever needed a filming permit for a government building?",
    "What did we decide about depicting Serena Williams in past productions?",
    "Is there a claim about McDonald's golden arches in this project?",
]


async def _run_risk_assessor(claim_id: str) -> None:
    runner = InMemoryRunner(agent=risk_assessor_agent, app_name=_RISK_ASSESSOR_APP)
    session = await runner.session_service.create_session(
        app_name=_RISK_ASSESSOR_APP,
        user_id="eval-user",
        state={
            "project_id": "eval-golden-legal",
            "jurisdictions": ["us", "gb"],
            "release_date": "2027-01-01",
        },
    )
    message = types.Content(
        role="user",
        parts=[types.Part(text=f"Assess risk for these already-verified claim_ids: {claim_id}")],
    )
    async for _event in runner.run_async(
        user_id="eval-user", session_id=session.id, new_message=message
    ):
        pass


def _claim_prompt(session: Any, claim_id: str) -> str:
    claim = ClaimRepo.require(session, claim_id)
    evidence = EvidenceRepo.latest_for_claim(session, claim_id)
    summary = json.dumps(evidence.output)[:1500] if evidence else "no evidence"
    return f"Claim: {claim.claim_text}\nCategory: {claim.category.value}\nEvidence: {summary}"


def _run_risk_assessor_eval() -> pd.DataFrame:
    cases = _seed_legal_project()
    claim_ids = [c["_claim_id"] for c in cases[:_RISK_CLAIM_COUNT]]

    async def _run_all() -> None:
        for claim_id in claim_ids:
            await _run_risk_assessor(claim_id)

    asyncio.run(_run_all())

    rows = []
    with session_scope() as session:
        for claim_id in claim_ids:
            risk = RiskRepo.get(session, claim_id)
            if risk is None:
                continue
            rows.append({"prompt": _claim_prompt(session, claim_id), "response": risk.rationale})

    dataset = pd.DataFrame(rows)
    task = EvalTask(
        dataset=dataset,
        metrics=[
            MetricPromptTemplateExamples.Pointwise.COHERENCE,
            MetricPromptTemplateExamples.Pointwise.GROUNDEDNESS,
        ],
    )
    result = task.evaluate()
    return result.summary_metrics


_CITATION_MARKER = re.compile(r"\[(\d+)\]")


def _citation_correctness(answer: str) -> float:
    """Every `[n]` marker in the answer must correspond to a real, listed citation
    (a numbered source line, or a Ledger/corpus/URL reference) -- a structural
    property, checked deterministically rather than by an LLM judge."""
    markers = {int(m) for m in _CITATION_MARKER.findall(answer)}
    if not markers:
        return 0.0
    # A cited source list is expected somewhere in the answer (the agent's own output
    # schema requires "citations in the form `[n] <source>`" -- ask_ouroboros.md).
    listed = {int(m) for m in re.findall(r"^\s*\[?\*?\[?(\d+)\]", answer, re.MULTILINE)}
    covered = markers & listed
    return len(covered) / len(markers)


def _ask_with_retry(question: str) -> str:
    # docs/DECISIONS.md #068: the remote Agent Engine worker occasionally dies
    # mid-request (a known, documented transient failure mode, not specific to this
    # script) -- one retry is enough in practice (confirmed live: a failed call
    # here succeeded immediately on a bare retry).
    try:
        return ask_question("demo", "", question)
    except RuntimeError:
        return ask_question("demo", "", question)


def _run_ask_ouroboros_eval() -> tuple[pd.DataFrame, float]:
    rows = []
    citation_scores = []
    for question in _ASK_QUESTIONS:
        answer = _ask_with_retry(question)
        rows.append({"prompt": question, "response": answer})
        citation_scores.append(_citation_correctness(answer))

    dataset = pd.DataFrame(rows)
    task = EvalTask(
        dataset=dataset,
        metrics=[MetricPromptTemplateExamples.Pointwise.QUESTION_ANSWERING_QUALITY],
    )
    result = task.evaluate()
    avg_citation_correctness = sum(citation_scores) / len(citation_scores)
    return result.summary_metrics, avg_citation_correctness


def main() -> int:
    print("Running RiskAssessor rationale quality eval...")
    risk_metrics = _run_risk_assessor_eval()
    print(risk_metrics)

    print("\nRunning AskOuroboros Q&A quality eval...")
    ask_metrics, citation_correctness = _run_ask_ouroboros_eval()
    print(ask_metrics)
    print(f"citation_correctness: {citation_correctness:.0%}")

    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _RESULTS_DIR / f"vertex-{date.today().isoformat()}.json"
    with open(out_path, "w") as f:
        json.dump(
            {
                "date": date.today().isoformat(),
                "risk_assessor": dict(risk_metrics),
                "ask_ouroboros": dict(ask_metrics),
                "ask_ouroboros_citation_correctness": citation_correctness,
            },
            f,
            indent=2,
            default=str,
        )
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
