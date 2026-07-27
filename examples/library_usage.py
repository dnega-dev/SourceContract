"""Run both packaged adapter suites through the SourceContract library."""

from sourcecontract.adapters import JSONReferenceAdapter, XMLReferenceAdapter
from sourcecontract.reports import render_text
from sourcecontract.runner import FixtureRunner


def main() -> int:
    runner = FixtureRunner()
    reports = [
        runner.run(JSONReferenceAdapter()),
        runner.run(XMLReferenceAdapter()),
    ]
    for report in reports:
        print(render_text(report), end="")
    return 0 if all(report.passed for report in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
