"""Unit tests for CodeGenerator.

Requirements: 1.5
"""

import pytest

from app.services.code_generator import CodeGenerator


@pytest.fixture
def generator() -> CodeGenerator:
    return CodeGenerator()


class TestGenerateDefault:
    def test_default_length_is_8(self, generator: CodeGenerator) -> None:
        code = generator.generate()
        assert len(code) == 8

    def test_default_code_is_alphanumeric(self, generator: CodeGenerator) -> None:
        code = generator.generate()
        assert code.isalnum()

    def test_default_all_chars_in_alphabet(self, generator: CodeGenerator) -> None:
        code = generator.generate()
        assert all(ch in CodeGenerator.ALPHABET for ch in code)


class TestGenerateWithLength:
    def test_generate_length_6(self, generator: CodeGenerator) -> None:
        code = generator.generate(6)
        assert len(code) == 6

    def test_generate_length_12(self, generator: CodeGenerator) -> None:
        code = generator.generate(12)
        assert len(code) == 12

    def test_generate_length_6_chars_in_alphabet(self, generator: CodeGenerator) -> None:
        code = generator.generate(6)
        assert all(ch in CodeGenerator.ALPHABET for ch in code)

    def test_generate_length_12_chars_in_alphabet(self, generator: CodeGenerator) -> None:
        code = generator.generate(12)
        assert all(ch in CodeGenerator.ALPHABET for ch in code)

    @pytest.mark.parametrize("length", [7, 8, 9, 10, 11])
    def test_generate_mid_range_lengths(self, generator: CodeGenerator, length: int) -> None:
        code = generator.generate(length)
        assert len(code) == length
        assert all(ch in CodeGenerator.ALPHABET for ch in code)


class TestGenerateInvalidLength:
    def test_length_below_minimum_raises(self, generator: CodeGenerator) -> None:
        with pytest.raises(ValueError):
            generator.generate(5)

    def test_length_above_maximum_raises(self, generator: CodeGenerator) -> None:
        with pytest.raises(ValueError):
            generator.generate(13)

    def test_length_zero_raises(self, generator: CodeGenerator) -> None:
        with pytest.raises(ValueError):
            generator.generate(0)


class TestGenerateRandomness:
    def test_consecutive_codes_differ(self, generator: CodeGenerator) -> None:
        """Codes should not be deterministically identical."""
        codes = {generator.generate() for _ in range(10)}
        assert len(codes) > 1
