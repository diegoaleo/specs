"""Property-based tests for the CodeGenerator service.

# Feature: python-url-shortener, Property 1: Short code generation correctness
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.code_generator import CodeGenerator


# ---------------------------------------------------------------------------
# Property 1: Short code generation correctness
# Validates: Requirements 1.5, 1.7
# ---------------------------------------------------------------------------

@given(length=st.integers(min_value=6, max_value=12))
@settings(max_examples=100)
def test_generated_code_characters_and_length(length: int) -> None:
    """Property 1: Short code generation correctness.

    For any length in 6-12, generate 100 codes and assert every character
    is in ALPHABET and the length matches.

    **Validates: Requirements 1.5, 1.7**
    """
    generator = CodeGenerator()

    for _ in range(100):
        code = generator.generate(length)

        # Length must match the requested length exactly (Requirement 1.5)
        assert len(code) == length, (
            f"Expected code of length {length}, got {len(code)!r} (code={code!r})"
        )

        # Every character must be in ALPHABET (Requirement 1.5)
        for char in code:
            assert char in CodeGenerator.ALPHABET, (
                f"Character {char!r} in code {code!r} is not in ALPHABET"
            )
