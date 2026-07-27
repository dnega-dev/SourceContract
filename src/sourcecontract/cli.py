"""Command-line interface for adapter conformance validation."""

import argparse
import importlib
import inspect
import json
from pathlib import Path
import sys
from typing import List, Optional, Sequence

from . import __version__
from .adapters import BUILTIN_ADAPTERS
from .errors import AdapterLoadError, SourceContractError
from .reports import render_report
from .runner import FixtureRepository, FixtureRunner
from .schema import get_schema, schema_names

EXIT_OK = 0
EXIT_NONCONFORMANT = 1
EXIT_USAGE = 2
EXIT_INTERNAL = 3


def load_adapter(spec: str) -> object:
    """Load a built-in adapter or ``module:attribute`` adapter target."""

    if spec in BUILTIN_ADAPTERS:
        return BUILTIN_ADAPTERS[spec]()
    if ":" not in spec:
        raise AdapterLoadError(
            "adapter must be a built-in name or module:attribute target"
        )
    module_name, attribute_path = spec.split(":", 1)
    if not module_name or not attribute_path:
        raise AdapterLoadError("adapter module and attribute must both be non-empty")
    try:
        target = importlib.import_module(module_name)
        for component in attribute_path.split("."):
            if not component or component.startswith("_"):
                raise AdapterLoadError("adapter attribute path contains an invalid component")
            target = getattr(target, component)
    except AdapterLoadError:
        raise
    except (ImportError, AttributeError) as exc:
        raise AdapterLoadError("cannot load adapter {!r}".format(spec), detail=str(exc)) from exc
    if inspect.isclass(target):
        try:
            target = target()
        except Exception as exc:
            raise AdapterLoadError(
                "cannot instantiate adapter class {!r}".format(spec), detail=str(exc)
            ) from exc
    return target


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sourcecontract",
        description="Validate official-source ingestion adapters against deterministic fixtures.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s {}".format(__version__))
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="run conformance fixtures")
    validate.add_argument(
        "adapter",
        help="built-in json/xml name or import target module:attribute",
    )
    validate.add_argument("--family", help="fixture family (must match adapter metadata)")
    validate.add_argument(
        "--fixture",
        action="append",
        default=[],
        metavar="ID",
        help="run only this fixture id; repeat to select several",
    )
    validate.add_argument(
        "--fixtures-dir",
        type=Path,
        help="use a caller-supplied fixture repository",
    )
    validate.add_argument(
        "--format",
        choices=("text", "json", "junit", "sarif"),
        default="text",
        help="report encoding (default: text)",
    )
    validate.add_argument(
        "--output",
        type=Path,
        metavar="PATH",
        help="write report to PATH instead of stdout",
    )

    fixtures = commands.add_parser("fixtures", help="inspect packaged fixtures")
    fixture_commands = fixtures.add_subparsers(dest="fixtures_command", required=True)
    fixture_list = fixture_commands.add_parser("list", help="list deterministic fixtures")
    fixture_list.add_argument("--family", help="filter by fixture family")
    fixture_list.add_argument(
        "--format", choices=("text", "json"), default="text"
    )
    fixture_list.add_argument("--fixtures-dir", type=Path)

    schema = commands.add_parser("schema", help="print a public JSON Schema")
    schema.add_argument(
        "name",
        nargs="?",
        choices=schema_names(),
        default="source-record",
    )
    schema.add_argument("--compact", action="store_true", help="omit indentation")
    return parser


def _write_output(rendered: str, destination: Optional[Path]) -> None:
    if destination is None:
        sys.stdout.write(rendered)
        return
    try:
        with destination.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(rendered)
    except OSError as exc:
        raise AdapterLoadError(
            "cannot write report to {}".format(destination), detail=str(exc)
        ) from exc


def _validate(args: argparse.Namespace) -> int:
    adapter = load_adapter(args.adapter)
    repository = FixtureRepository(args.fixtures_dir)
    report = FixtureRunner(repository).run(
        adapter,
        family=args.family,
        fixture_ids=args.fixture or None,
    )
    _write_output(render_report(report, args.format), args.output)
    return EXIT_OK if report.passed else EXIT_NONCONFORMANT


def _list_fixtures(args: argparse.Namespace) -> int:
    fixtures = FixtureRunner(FixtureRepository(args.fixtures_dir)).fixtures(
        family=args.family
    )
    if args.format == "json":
        rendered = json.dumps(
            {"count": len(fixtures), "fixtures": [fixture.to_dict() for fixture in fixtures]},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n"
    else:
        lines = [
            "{}\t{}\t{}\t{}".format(
                fixture.fixture_id,
                fixture.family,
                ",".join(fixture.tags) or "-",
                fixture.title,
            )
            for fixture in fixtures
        ]
        rendered = "\n".join(lines) + "\n"
    sys.stdout.write(rendered)
    return EXIT_OK


def _schema(args: argparse.Namespace) -> int:
    indent = None if args.compact else 2
    separators = (",", ":") if args.compact else None
    sys.stdout.write(
        json.dumps(
            get_schema(args.name),
            ensure_ascii=False,
            indent=indent,
            separators=separators,
            sort_keys=True,
        )
        + "\n"
    )
    return EXIT_OK


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the CLI and return a documented process status code."""

    parser = _parser()
    try:
        args = parser.parse_args(argv)
        if args.command == "validate":
            return _validate(args)
        if args.command == "fixtures" and args.fixtures_command == "list":
            return _list_fixtures(args)
        if args.command == "schema":
            return _schema(args)
        parser.error("unknown command")
    except SourceContractError as exc:
        sys.stderr.write("sourcecontract: {}: {}\n".format(exc.code, exc))
        return EXIT_USAGE
    except (OSError, ValueError, KeyError) as exc:
        sys.stderr.write("sourcecontract: {}\n".format(exc))
        return EXIT_USAGE
    except Exception as exc:  # last-resort stable CLI boundary
        sys.stderr.write(
            "sourcecontract: INTERNAL_ERROR: {}: {}\n".format(
                exc.__class__.__name__, exc
            )
        )
        return EXIT_INTERNAL
    return EXIT_INTERNAL
