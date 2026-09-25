"""Shared summarizer prompt construction (train + evaluate must match).

Two format fixes from the v0.1.0 evaluation:
- the instruct model is used through its NATIVE chat template;
- a one-shot formatted exemplar teaches the section layout at inference.
"""

EXEMPLAR_INPUT = (
    "TITLE: Summer School on AI Policy 2026\n\n"
    "OPPORTUNITY TEXT:\n"
    "The European Institute invites applications for its one-week summer school "
    "on AI policy and governance, held in Brussels in June 2026. The programme "
    "is open to master's students and early-career researchers worldwide. "
    "Tuition is waived; participants cover their own travel and accommodation. "
    "Application deadline: March 1, 2026."
)
EXEMPLAR_SUMMARY = (
    "DEADLINE\n"
    "- March 1, 2026; status: explicit\n\n"
    "MANDATORY\n"
    "- Master's student or early-career researcher\n\n"
    "TARGET GROUP\n"
    "- Open to applicants worldwide\n\n"
    "FUNDING / BENEFITS\n"
    "- Tuition waived; travel and accommodation self-funded\n\n"
    "APPLICATION\n"
    "- Apply before March 1, 2026\n\n"
    "SUMMARY\n"
    "One-week AI policy summer school in Brussels (June 2026), open worldwide "
    "to master's students and early-career researchers. Tuition waived; travel "
    "self-funded. Deadline March 1, 2026."
)

INSTRUCTIONS = (
    "Summarize the following opportunity posting as high-signal intelligence. "
    "Use sections DEADLINE / MANDATORY / RESTRICTIONS / TARGET GROUP / "
    "FUNDING / BENEFITS / APPLICATION / OTHER IMPORTANT CONDITIONS / SUMMARY "
    "(omit empty sections), at most 150 words, and never invent information."
)


def build_user_message(input_text: str) -> str:
    """User chat message: instructions + one-shot exemplar + the real posting."""
    return (
        f"{INSTRUCTIONS}\n\n"
        "=== EXAMPLE ===\n"
        f"{EXEMPLAR_INPUT}\n\n"
        f"CORRECT SUMMARY:\n{EXEMPLAR_SUMMARY}\n"
        "=== END EXAMPLE ===\n\n"
        f"Now summarize this opportunity the same way:\n\n{input_text}"
    )


def render_prompt(tokenizer, input_text: str) -> str:
    """Render through the model's native chat template with a generation prompt."""
    return tokenizer.apply_chat_template(
        [{"role": "user", "content": build_user_message(input_text)}],
        tokenize=False,
        add_generation_prompt=True,
    )


def build_raw_prompt(input_text: str) -> str:
    """Flat (non-chat) prompt ending in a stable boundary marker.

    The trailing newline after the TARGET OUTPUT marker makes the
    prompt/completion token boundary deterministic (TRL mask-drift root
    cause); use with the matching evaluator/serving path so train and
    inference are identical.
    """
    nl = chr(10)
    return (
        INSTRUCTIONS + nl + nl
        + "=== EXAMPLE ===" + nl
        + EXEMPLAR_INPUT + nl + nl
        + "CORRECT SUMMARY:" + nl + EXEMPLAR_SUMMARY + nl
        + "=== END EXAMPLE ===" + nl + nl
        + "Now summarize this opportunity the same way:" + nl + nl
        + "OPPORTUNITY:" + nl + input_text + nl + nl
        + "TARGET OUTPUT:" + nl
    )
