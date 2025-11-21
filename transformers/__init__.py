from __future__ import annotations

import typing as t


class AutoModelForCausalLM:  # minimal stub for tests
    @classmethod
    def from_pretrained(cls, *args: t.Any, **kwargs: t.Any) -> t.Any:  # noqa: D401, ANN001
        return cls()

    def generate(self, *args: t.Any, **kwargs: t.Any) -> t.Any:  # noqa: D401, ANN001
        return []


class AutoTokenizer:  # minimal stub for tests
    @classmethod
    def from_pretrained(cls, *args: t.Any, **kwargs: t.Any) -> t.Any:  # noqa: D401, ANN001
        return cls()

    def __call__(self, *args: t.Any, **kwargs: t.Any) -> t.Any:  # noqa: D401, ANN001
        return {"input_ids": [[1, 2, 3]]}

    def decode(self, *args: t.Any, **kwargs: t.Any) -> str:  # noqa: D401, ANN001
        return ""

    eos_token_id: int = 0
