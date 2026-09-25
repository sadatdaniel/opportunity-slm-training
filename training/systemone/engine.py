"""System-One decision layer: typed, non-autoregressive decision primitives.

Implements the Jev/Von-inspired protocol (brief sections 4A, 4B, 4C, 43):

- Noul: one binary proposition over a state -> P(true) in [0, 1]. Never
  generates yes/no text.
- Choice: one categorical question -> probability distribution over explicit
  criteria + a confidence signal distinct from the winning probability.

Mechanics (v0 honest prototype, documented limitation):
Each question is scored by comparing criterion texts against the state with
the backbone LM in a single non-autoregressive forward pass per criterion:
score = mean log-probability the LM assigns to the criterion text conditioned
on the state prompt. Noul probability = softmax over {true-criterion,
false-criterion} scores. Choice probabilities = softmax over criterion
scores. Confidence = top1-top2 probability margin (Von's definition,
brief section 4C).

Known limitation (brief 4B allows this for the first prototype): the state is
re-tokenized for every question; there is no shared-state KV reuse yet. The
batch endpoint measures and reports this honestly (state_tokens_processed =
questions x state_tokens) rather than claiming single-pass efficiency.

The layer is model-agnostic: any HuggingFace causal LM works, which lets the
same code run the base Supra model, our fine-tuned decision model, and CI
tests with a tiny random model.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import torch
import torch.nn.functional as F

NOUL_TRUE = "true"
NOUL_FALSE = "false"


@dataclass
class NoulQuestion:
    instructions: str
    criteria: dict  # {"true": str, "false": str}

    def validate(self) -> None:
        if NOUL_TRUE not in self.criteria or NOUL_FALSE not in self.criteria:
            raise ValueError("noul question requires criteria 'true' and 'false'")


@dataclass
class ChoiceQuestion:
    instructions: str
    criteria: dict  # label -> description

    def validate(self) -> None:
        if len(self.criteria) < 2:
            raise ValueError("choice question requires at least two criteria")


@dataclass
class NoulAnswer:
    type: str = "noul"
    noul: float = 0.5  # P(proposition true); near 1 -> yes, near 0 -> no, ~0.5 -> uncertain
    scores: dict = field(default_factory=dict)  # per-criterion raw scores (debug)


@dataclass
class ChoiceAnswer:
    type: str = "choice"
    choice: str = ""
    probabilities: dict = field(default_factory=dict)
    # Default definition matches the formula shipped in both TypeSafe's docs
    # and Von's code: confidence = clamp((n*p_max - 1) / (n - 1)), anchored at
    # uniform=0 and certainty=1. Von's README describes a plain top1-top2
    # margin, which equals this only for n=2; we keep the margin available as
    # its own field and choose empirically (brief 4C). No Jev parity claimed.
    confidence: float = 0.0
    top_probability: float = 0.0
    second_probability: float = 0.0
    top1_top2_margin: float = 0.0
    entropy: float = 0.0
    scores: dict = field(default_factory=dict)


class SystemOneEngine:
    """Scores Noul/Choice questions against a state with any causal LM."""

    def __init__(self, model, tokenizer, *, device: str | None = None, max_state_words: int = 600, max_length: int = 1024):
        self.model = model
        self.tokenizer = tokenizer
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.model.eval()
        self.max_state_words = max_state_words
        self.max_length = max_length

    def _prompt(self, state: str, criterion: str, question: NoulQuestion | ChoiceQuestion) -> str:
        state = " ".join(state.split()[: self.max_state_words])
        return (
            "Opportunity posting:\n"
            f"{state}\n\n"
            f"Question: {question.instructions}\n"
            f"Statement to evaluate: {criterion}\n"
        )

    @torch.no_grad()
    def _score(self, prompts: list[str], criterion_texts: list[str]) -> list[float]:
        """Mean log-probability of each criterion text given its prompt.

        One forward pass per (prompt, criterion) pair, batched across pairs.
        Non-autoregressive scoring: nothing is generated.
        """
        scores: list[float] = []
        batch_size = 8
        for start in range(0, len(prompts), batch_size):
            batch_prompts = prompts[start : start + batch_size]
            batch_criteria = criterion_texts[start : start + batch_size]
            full = [p + c for p, c in zip(batch_prompts, batch_criteria)]
            prompt_lens = [len(self.tokenizer.encode(p, add_special_tokens=False)) for p in batch_prompts]
            enc = self.tokenizer(
                full, return_tensors="pt", padding=True, truncation=True, max_length=self.max_length
            ).to(self.device)
            input_ids = enc["input_ids"]
            attention_mask = enc["attention_mask"]
            logits = self.model(input_ids=input_ids, attention_mask=attention_mask).logits
            # token t is predicted by position t-1
            log_probs = F.log_softmax(logits[:, :-1], dim=-1)
            targets = input_ids[:, 1:]
            token_log_probs = log_probs.gather(-1, targets.unsqueeze(-1)).squeeze(-1)
            for row, prompt_len in enumerate(prompt_lens):
                # score only the criterion continuation tokens of this row
                seq_len = int(attention_mask[row].sum())
                criterion_len = seq_len - prompt_len
                if criterion_len <= 0:
                    # criterion fully truncated: deterministic neutral score,
                    # never -inf (inf - inf -> NaN would poison the response)
                    scores.append(-1.0e9)
                    continue
                relevant = token_log_probs[row, prompt_len - 1 : seq_len - 1]
                scores.append(float(relevant.mean()))
        return scores

    def answer_noul(self, state: str, question: NoulQuestion) -> NoulAnswer:
        question.validate()
        criteria = [question.criteria[NOUL_TRUE], question.criteria[NOUL_FALSE]]
        prompts = [self._prompt(state, c, question) for c in criteria]
        scores = self._score(prompts, criteria)
        probs = F.softmax(torch.tensor(scores, dtype=torch.float64), dim=0)
        return NoulAnswer(noul=float(probs[0]), scores={"true": scores[0], "false": scores[1]})

    def answer_choice(self, state: str, question: ChoiceQuestion) -> ChoiceAnswer:
        question.validate()
        labels = list(question.criteria)
        criteria = [question.criteria[label] for label in labels]
        prompts = [self._prompt(state, c, question) for c in criteria]
        scores = self._score(prompts, criteria)
        probs = F.softmax(torch.tensor(scores, dtype=torch.float64), dim=0)
        probabilities = {label: float(p) for label, p in zip(labels, probs)}
        ranked = sorted(probabilities.items(), key=lambda kv: -kv[1])
        top_probability = ranked[0][1]
        second_probability = ranked[1][1]
        import math

        entropy = -sum(p * math.log(p) for p in probabilities.values() if p > 0)
        margin = top_probability - second_probability
        n = len(probabilities)
        # TypeSafe/Von-shipped definition: 0 at uniform, 1 at certainty
        confidence = max(0.0, min(1.0, (n * top_probability - 1) / (n - 1)))
        return ChoiceAnswer(
            choice=ranked[0][0],
            probabilities=probabilities,
            confidence=confidence,
            top_probability=top_probability,
            second_probability=second_probability,
            top1_top2_margin=margin,
            entropy=entropy,
            scores=dict(zip(labels, scores)),
        )

    def answer_batch(self, state: str, questions: dict[str, NoulQuestion | ChoiceQuestion]) -> dict[str, NoulAnswer | ChoiceAnswer]:
        """Many independent questions over one shared state.

        Questions are scored independently: answers are identical to calling
        answer_noul/answer_choice separately (regression-tested, brief 4B).
        """
        return {
            qid: self.answer_noul(state, q) if isinstance(q, NoulQuestion) else self.answer_choice(state, q)
            for qid, q in questions.items()
        }
