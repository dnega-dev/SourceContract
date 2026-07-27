"""Deterministic text, JSON, JUnit XML, and SARIF report renderers."""

import json
from typing import Callable, Dict, Iterable, List
from urllib.parse import quote
import xml.etree.ElementTree as ET

from .invariants import RULES
from .result import Issue, ValidationReport


def render_text(report: ValidationReport) -> str:
    lines = [
        "SourceContract {} validation".format(report.contract_version),
        "Adapter: {} (contract {})".format(
            report.adapter_name, report.adapter_contract_version
        ),
        "",
    ]
    for result in report.fixture_results:
        lines.append("{} {} — {}".format("PASS" if result.passed else "FAIL", result.fixture_id, result.title))
        for issue in result.issues:
            location = " [{}]".format(issue.record_id) if issue.record_id else ""
            lines.append("  {} {}{}: {}".format(issue.level.upper(), issue.rule_id, location, issue.message))
    lines.extend(
        [
            "",
            "Result: {}".format("PASS" if report.passed else "FAIL"),
            "Fixtures: {} passed, {} failed, {} total; {} issues".format(
                report.passed_count,
                report.failed_count,
                report.fixture_count,
                report.issue_count,
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def render_json(report: ValidationReport) -> str:
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_junit(report: ValidationReport) -> str:
    suite = ET.Element(
        "testsuite",
        {
            "name": "SourceContract.{}".format(report.adapter_name),
            "tests": str(report.fixture_count),
            "failures": str(report.failed_count),
            "errors": "0",
            "skipped": "0",
            "time": "0",
        },
    )
    properties = ET.SubElement(suite, "properties")
    ET.SubElement(properties, "property", {"name": "contract_version", "value": report.contract_version})
    ET.SubElement(
        properties,
        "property",
        {"name": "adapter_contract_version", "value": report.adapter_contract_version},
    )
    for result in report.fixture_results:
        case = ET.SubElement(
            suite,
            "testcase",
            {
                "classname": "sourcecontract.fixtures.{}".format(result.family),
                "name": result.fixture_id,
                "time": "0",
            },
        )
        if not result.passed:
            error_issues = [issue for issue in result.issues if issue.level == "error"]
            rule_ids = ",".join(sorted({issue.rule_id for issue in error_issues}))
            failure = ET.SubElement(
                case,
                "failure",
                {
                    "message": "{} conformance issue(s)".format(len(error_issues)),
                    "type": rule_ids,
                },
            )
            failure.text = "\n".join(
                "{}: {}{}".format(
                    issue.rule_id,
                    issue.message,
                    " (record {})".format(issue.record_id) if issue.record_id else "",
                )
                for issue in error_issues
            )
    xml_body = ET.tostring(suite, encoding="unicode", short_empty_elements=True)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_body + "\n"


def render_sarif(report: ValidationReport) -> str:
    used_rule_ids = sorted(
        {
            issue.rule_id
            for fixture in report.fixture_results
            for issue in fixture.issues
        }
    )
    rules = [
        {
            "id": rule_id,
            "name": RULES.get(rule_id, rule_id).replace(" ", ""),
            "shortDescription": {"text": RULES.get(rule_id, rule_id)},
            "defaultConfiguration": {"level": "error"},
        }
        for rule_id in used_rule_ids
    ]
    results: List[Dict[str, object]] = []
    for fixture in report.fixture_results:
        for issue in fixture.issues:
            location: Dict[str, object] = {
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": "sourcecontract-fixture:///{}".format(
                            quote(fixture.fixture_id, safe="")
                        )
                    }
                }
            }
            if issue.record_id is not None:
                location["logicalLocations"] = [
                    {"name": issue.record_id, "kind": "record"}
                ]
            results.append(
                {
                    "ruleId": issue.rule_id,
                    "level": issue.level,
                    "message": {"text": issue.message},
                    "locations": [location],
                    "properties": {
                        "fixture_id": fixture.fixture_id,
                        "fixture_family": fixture.family,
                    },
                }
            )
    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "SourceContract",
                        "semanticVersion": report.contract_version,
                        "rules": rules,
                    }
                },
                "automationDetails": {"id": "sourcecontract/{}".format(report.adapter_name)},
                "results": results,
            }
        ],
    }
    return json.dumps(sarif, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


_RENDERERS: Dict[str, Callable[[ValidationReport], str]] = {
    "text": render_text,
    "json": render_json,
    "junit": render_junit,
    "sarif": render_sarif,
}


def render_report(report: ValidationReport, format_name: str) -> str:
    try:
        renderer = _RENDERERS[format_name]
    except KeyError as exc:
        raise ValueError(
            "unsupported report format {!r}; choose {}".format(
                format_name, ", ".join(sorted(_RENDERERS))
            )
        ) from exc
    return renderer(report)
