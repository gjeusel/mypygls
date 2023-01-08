import pytest

from mypygls.server import LINE_PATTERN


class TestDiagnosticParsing:
    regex_testcases = (
        # should handle full diagnostic:
        (
            'test.py:1:1: error: Library stubs not installed for "requests" (or incompatible with Python 3.9)  [import]',
            (
                "test.py",
                "1",
                "1",
                "error",
                'Library stubs not installed for "requests" (or incompatible with Python 3.9)  [import]',
            ),
        ),
        # should diagnostic without code:
        (
            'some/path-to_.py:2:1: note: Hint: "python3 -m pip install types-requests"',
            (
                "some/path-to_.py",
                "2",
                "1",
                "Hint",
                '"python3 -m pip install types-requests"',
            ),
        ),
        # should handle diagnostic with no column or error code:
        (
            'tests/example.py:3: error: Unused "type: ignore" comment',
            ("tests/example.py", "3", None, "error", 'Unused "type: ignore" comment'),
        ),
    )

    @pytest.mark.parametrize("raw, expected", regex_testcases)
    def test_diagnostic_parse_regex(self, raw, expected):
        match = LINE_PATTERN.match(raw)

        assert match is not None
        assert match.groups() == expected
