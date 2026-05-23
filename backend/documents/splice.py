"""Pure splice helper for accepting a track-changes Suggestion.

Pulled out of `backend/routes/collab.py` so the validation behaviour
is testable without spinning up Postgres / FastAPI / pydantic. The
route handler imports `apply_suggestion` and lets the exceptions
propagate.

The validations we run before splicing:

  1. range bounds make sense (non-negative, end ≥ start, end ≤ len).
  2. base_text still matches what's at that range in the current
     version. If the document was edited under the suggestion this
     will fail — accepting blindly would silently produce garbage
     because Python's slice notation never raises on out-of-bounds.

Insert-style suggestions (range_start == range_end, base_text empty)
only need the bounds check; there's nothing to compare against.
"""
from __future__ import annotations


class StaleSuggestionError(Exception):
    """The suggestion's recorded range / base_text no longer matches the
    current version of the document. The caller should surface this as
    a 409 Conflict so the user knows the suggestion is out of date.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def apply_suggestion(
    *,
    current: str,
    range_start: int,
    range_end: int,
    base_text: str,
    proposed_text: str,
) -> str:
    """Validate + splice. Returns the new document content.

    Raises StaleSuggestionError when the suggestion no longer applies
    cleanly to `current`. The caller (collab.py) converts that into a
    409 Conflict response.
    """
    if range_start < 0 or range_end < range_start:
        raise StaleSuggestionError("suggestion range is invalid")
    if range_end > len(current):
        raise StaleSuggestionError(
            f"document changed since suggestion was created — "
            f"range {range_start}..{range_end} no longer fits "
            f"(doc length {len(current)})"
        )
    # Insert-style: empty base_text + collapsed range. Nothing to compare.
    if base_text:
        actual = current[range_start:range_end]
        if actual != base_text:
            raise StaleSuggestionError(
                "document changed since suggestion was created — text at "
                "the suggested range no longer matches the suggestion's "
                "base_text; create a new suggestion against the current "
                "version."
            )
    return current[:range_start] + proposed_text + current[range_end:]
