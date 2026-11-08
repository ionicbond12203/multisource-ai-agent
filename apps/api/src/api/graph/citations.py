"""
Checks the citation markers in a drafted answer.

The model is told to cite sources as [1], [2] …, but it can still invent a
number or cite nothing. This module finds every marker, drops the ones that
don't match a real source, and reports what it found so the answer can be
marked grounded or not.
"""

import re
from collections.abc import Collection
from dataclasses import dataclass

# Matches [1], [12] and grouped forms such as [1, 2] or [1,2,3].
_MARKER = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


@dataclass(frozen=True)
class CitationCheck:
    text: str  # answer with invalid markers removed and groups split: [1, 2] → [1][2]
    cited: frozenset[int]  # valid source numbers the answer uses
    invalid: frozenset[int]  # numbers that matched no source and were removed

    @property
    def grounded(self) -> bool:
        return bool(self.cited) and not self.invalid


def check_citations(answer: str, valid_numbers: Collection[int]) -> CitationCheck:
    valid = set(valid_numbers)
    cited: set[int] = set()
    invalid: set[int] = set()

    def rewrite(match: re.Match[str]) -> str:
        numbers = [int(part) for part in match.group(1).split(",")]
        kept = [n for n in numbers if n in valid]
        cited.update(kept)
        invalid.update(n for n in numbers if n not in valid)
        return "".join(f"[{n}]" for n in kept)

    text = _MARKER.sub(rewrite, answer)
    # Removing a marker can leave a space before punctuation: "fact [9]." → "fact ."
    text = re.sub(r" +([.,;:!?])", r"\1", text).strip()
    return CitationCheck(text=text, cited=frozenset(cited), invalid=frozenset(invalid))
