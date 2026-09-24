"""Opportunity Intelligence API (brief sections 1, 30, 31).

Strict specialist endpoints only — no chat/completions/generate:

    GET  /health
    GET  /version
    GET  /v1/capabilities
    POST /v1/summarize      generative (fixed task instructions; caller input is content only)
    POST /v1/categorize     Choice over taxonomy categories (decision layer)
    POST /v1/noul           one binary question over a state (decision layer)
    POST /v1/systemone      one state + many typed questions (Noul/Choice; Score later)

Decision endpoints never generate prose: they return fixed typed schemas
produced by application code. The decision layer currently runs the model
from the task registry (base Supra until trained artifacts are registered).
`/v1/categorize` and `/v1/noul` are convenience wrappers over the same
System-One engine used by `/v1/systemone` (brief 4B).
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from project.freeze_corpus import PROJECT_ROOT
from training.common.datasets import load_taxonomy_categories
from training.systemone.engine import ChoiceQuestion, NoulQuestion, SystemOneEngine

REGISTRY_PATH = PROJECT_ROOT / "config" / "task_registry.yaml"

app = FastAPI(title="Opportunity Intelligence", version="0.1.0")
_engine: SystemOneEngine | None = None


def registry() -> dict:
    return yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))


def get_engine() -> SystemOneEngine:
    """Lazily load the decision model named by the registry.

    `base:<hf-id>` loads the untouched model; `models/...` loads a trained
    artifact directory (swap without code changes, brief 29).
    """
    global _engine
    if _engine is None:
        from transformers import AutoModelForCausalLM, AutoTokenizer

        spec = registry()["systemone"]["model"]
        source = spec.split("base:", 1)[1] if spec.startswith("base:") else str(PROJECT_ROOT / spec)
        tokenizer = AutoTokenizer.from_pretrained(source)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        model = AutoModelForCausalLM.from_pretrained(source)
        _engine = SystemOneEngine(model, tokenizer)
    return _engine


# -- request/response schemas -------------------------------------------------


class SummarizeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=60000)


class QuestionSpec(BaseModel):
    type: str
    instructions: str
    criteria: dict[str, str]


class SystemOneRequest(BaseModel):
    state: str = Field(min_length=1, max_length=60000)
    questions: dict[str, QuestionSpec]


class NoulRequest(BaseModel):
    state: str = Field(min_length=1, max_length=60000)
    instructions: str
    criteria_true: str
    criteria_false: str


class CategorizeRequest(BaseModel):
    state: str = Field(min_length=1, max_length=60000)


# -- helpers -------------------------------------------------------------------


def _question_from_spec(qid: str, spec: QuestionSpec):
    if spec.type == "noul":
        return NoulQuestion(instructions=spec.instructions, criteria=spec.criteria)
    if spec.type == "choice":
        return ChoiceQuestion(instructions=spec.instructions, criteria=spec.criteria)
    raise HTTPException(status_code=422, detail=f"question {qid!r}: unsupported type {spec.type!r} (noul/choice; score later)")


def _answer_payload(answer) -> dict:
    if answer.type == "noul":
        return {"type": "noul", "noul": answer.noul}
    return {
        "type": "choice",
        "choice": answer.choice,
        "confidence": answer.confidence,
        "probabilities": answer.probabilities,
        "top_probability": answer.top_probability,
        "top1_top2_margin": answer.top1_top2_margin,
        "entropy": answer.entropy,
    }


# -- endpoints ------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/version")
def version() -> dict:
    reg = registry()
    versions = {}
    for capability, spec in reg.items():
        model = spec["model"]
        versions[capability] = "base" if model.startswith("base:") else model.rstrip("/").split("/")[-1]
    return {**versions, "taxonomy": "v1"}


@app.get("/v1/capabilities")
def capabilities() -> dict:
    return {"capabilities": ["summarize", "categorize", "noul", "systemone"]}


@app.post("/v1/systemone")
def systemone(request: SystemOneRequest) -> dict:
    if not request.questions:
        raise HTTPException(status_code=422, detail="at least one question is required")
    engine = get_engine()
    questions = {qid: _question_from_spec(qid, spec) for qid, spec in request.questions.items()}
    answers = engine.answer_batch(request.state, questions)
    return {"answers": {qid: _answer_payload(a) for qid, a in answers.items()}}


@app.post("/v1/noul")
def noul(request: NoulRequest) -> dict:
    question = NoulQuestion(
        instructions=request.instructions,
        criteria={"true": request.criteria_true, "false": request.criteria_false},
    )
    answer = get_engine().answer_noul(request.state, question)
    return _answer_payload(answer)


@app.post("/v1/categorize")
def categorize(request: CategorizeRequest) -> dict:
    """Choice over the taxonomy categories with fixed criteria descriptions."""
    criteria = json.loads(
        (PROJECT_ROOT / "config" / "category_criteria.json").read_text(encoding="utf-8")
    ) if (PROJECT_ROOT / "config" / "category_criteria.json").exists() else {
        category: f"This posting is primarily a {category.replace('_', ' ')} opportunity."
        for category in load_taxonomy_categories()
    }
    question = ChoiceQuestion(
        instructions="Which opportunity category best describes this posting?",
        criteria={k: v for k, v in criteria.items() if k in load_taxonomy_categories()},
    )
    answer = get_engine().answer_choice(request.state, question)
    return _answer_payload(answer)


@app.post("/v1/summarize")
def summarize(request: SummarizeRequest) -> dict:
    """Generative endpoint with immutable task instructions.

    The caller's text is treated purely as opportunity content (brief 30):
    it is embedded in the user message, never into the system prompt.
    """
    from transformers import pipeline

    engine = get_engine()
    prompt = (
        "Summarize the following opportunity posting as high-signal intelligence.\n"
        "Use sections MANDATORY / RESTRICTIONS / IMPORTANT / PREFERRED / SUMMARY "
        "(omit empty sections), at most 150 words, and never invent information.\n\n"
        f"OPPORTUNITY POSTING:\n{request.text}"
    )
    summarizer = pipeline("text-generation", model=engine.model, tokenizer=engine.tokenizer, device=engine.device)
    output = summarizer(prompt, max_new_tokens=300, do_sample=False, return_full_text=False)
    return {"summary": output[0]["generated_text"].strip()}
