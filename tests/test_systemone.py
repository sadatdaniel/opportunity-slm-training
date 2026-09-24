"""Tests for the System-One decision layer (brief sections 4A, 4B, 4C).

Uses a tiny random-weight causal LM so tests run offline and deterministically.
Skip logic: if no cached tokenizer is available offline, tests are skipped
(the layer itself is model-agnostic).
"""

import math

import pytest
import torch

from training.systemone.engine import (
    ChoiceQuestion,
    NoulQuestion,
    SystemOneEngine,
)

STATE_YES = "Applicants must demonstrate German proficiency at B2 or above. Funding of EUR 1,200 per month is provided. Application deadline: 27 September 2026."
STATE_NO = "Knowledge of German is advantageous but not required. This opportunity is unfunded; no application deadline is stated."

NOUL_GERMAN = NoulQuestion(
    instructions="Is German mandatory for this opportunity?",
    criteria={
        "true": "The opportunity requires German language proficiency as a mandatory condition.",
        "false": "German proficiency is not a mandatory condition for this opportunity.",
    },
)

CHOICE_FUNDING = ChoiceQuestion(
    instructions="Which funding situation best describes this opportunity?",
    criteria={
        "funded": "The opportunity provides direct financial support such as a stipend, salary, or grant.",
        "unfunded": "The opportunity provides no direct financial support.",
        "fee_charging": "Participants must pay to take part in the opportunity.",
    },
)


@pytest.fixture(scope="module")
def engine():
    pytest.importorskip("transformers")
    try:
        import os

        from transformers import AutoTokenizer, GPT2Config, GPT2LMHeadModel

        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        tokenizer = AutoTokenizer.from_pretrained("SupraLabs/Supra2-100M-Instruct")
    except Exception:  # noqa: BLE001 - offline machines skip rather than fail
        pytest.skip("no cached tokenizer available offline")
    tokenizer.pad_token = tokenizer.eos_token or tokenizer.pad_token
    vocab_size = max(len(tokenizer), max(tokenizer.get_vocab().values()) + 1)
    config = GPT2Config(vocab_size=vocab_size, n_layer=1, n_head=2, n_embd=32, n_positions=256)
    model = GPT2LMHeadModel(config)
    torch.manual_seed(7)
    return SystemOneEngine(model, tokenizer, max_state_words=40, max_length=256)


def test_noul_returns_probability_in_range(engine):
    for state in (STATE_YES, STATE_NO):
        answer = engine.answer_noul(state, NOUL_GERMAN)
        assert 0.0 <= answer.noul <= 1.0
        assert set(answer.scores) == {"true", "false"}


def test_choice_returns_distribution(engine):
    answer = engine.answer_choice(STATE_YES, CHOICE_FUNDING)
    total = sum(answer.probabilities.values())
    assert math.isclose(total, 1.0, rel_tol=1e-9)
    assert answer.choice in CHOICE_FUNDING.criteria
    assert 0.0 <= answer.confidence <= 1.0
    assert math.isclose(answer.top_probability, max(answer.probabilities.values()), rel_tol=1e-9)


def test_choice_confidence_uses_typesafe_normalized_formula(engine):
    """Both TypeSafe's docs and Von's shipped code use (n*p_max - 1)/(n - 1).

    Von's README's plain top1-top2 margin equals this only at n=2; the margin
    stays available as its own field (brief 4C: document the definition).
    """
    answer = engine.answer_choice(STATE_YES, CHOICE_FUNDING)
    ranked = sorted(answer.probabilities.values(), reverse=True)
    n = len(ranked)
    expected = max(0.0, min(1.0, (n * ranked[0] - 1) / (n - 1)))
    assert math.isclose(answer.confidence, expected, rel_tol=1e-9)
    assert math.isclose(answer.top1_top2_margin, ranked[0] - ranked[1], rel_tol=1e-9)
    assert answer.confidence <= answer.top_probability


def test_question_validation(engine):
    with pytest.raises(ValueError):
        engine.answer_noul(STATE_YES, NoulQuestion(instructions="x", criteria={"true": "y"}))
    with pytest.raises(ValueError):
        engine.answer_choice(STATE_YES, ChoiceQuestion(instructions="x", criteria={"a": "b"}))


def test_batch_matches_single_calls_exactly(engine):
    """The critical System-One invariant (brief 4B): batching must not change answers."""
    questions = {
        "german_mandatory": NOUL_GERMAN,
        "funding": CHOICE_FUNDING,
        "german_mandatory_again": NOUL_GERMAN,
    }
    for state in (STATE_YES, STATE_NO):
        batched = engine.answer_batch(state, questions)
        for qid, question in questions.items():
            if isinstance(question, NoulQuestion):
                single = engine.answer_noul(state, question)
                assert batched[qid].noul == pytest.approx(single.noul, abs=0.0)
            else:
                single = engine.answer_choice(state, question)
                assert batched[qid].probabilities == single.probabilities
                assert batched[qid].confidence == single.confidence


def test_batch_answers_are_question_independent(engine):
    """Adding other questions to a batch must not alter an answer (brief 4B)."""
    solo = engine.answer_batch(STATE_YES, {"funding": CHOICE_FUNDING})
    crowded = engine.answer_batch(STATE_YES, {"funding": CHOICE_FUNDING, "german": NOUL_GERMAN})
    assert solo["funding"].probabilities == crowded["funding"].probabilities


def test_noul_scores_are_probabilities_of_criterion_text(engine):
    """Noul = softmax over the two criterion scores, true first (brief 4A)."""
    import torch.nn.functional as F

    answer = engine.answer_noul(STATE_YES, NOUL_GERMAN)
    probs = F.softmax(torch.tensor([answer.scores["true"], answer.scores["false"]], dtype=torch.float64), dim=0)
    assert answer.noul == pytest.approx(float(probs[0]), rel=1e-9)
