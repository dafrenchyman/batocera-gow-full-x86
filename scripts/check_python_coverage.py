"""Enforce fresh, complete application line coverage independently of branches.

Adapted from ProjectTemplate's line-count CLI. Unlike its tooling-only profile,
this application never accepts empty source or an absent measurement.
"""

import argparse
import hashlib
import json
import math
import sys
import tomllib
from pathlib import Path

from coverage import Coverage
from coverage.data import combinable_files
from coverage.exceptions import CoverageException

PERCENT_SCALE = 100
MINIMUM_LINES = 80
RECEIPT_VERSION = 2


class InvalidReportError(ValueError):
    """The supplied evidence cannot establish application coverage."""


def object_value(value: object) -> dict[str, object]:
    """Require a JSON object before reading external report fields."""
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        message = "Expected a JSON object."
        raise InvalidReportError(message)
    return {str(key): item for key, item in value.items()}


def integer(value: object) -> int:
    """Reject booleans, fractions and negative measurement counts."""
    if type(value) is not int or value < 0:
        message = "Coverage counts must be nonnegative integers."
        raise InvalidReportError(message)
    return value


def line_numbers(value: object) -> set[int]:
    """Require positive, distinct executable line numbers."""
    if not isinstance(value, list):
        message = "Coverage line numbers must be a list."
        raise InvalidReportError(message)
    result = {integer(item) for item in value}
    if 0 in result or len(result) != len(value):
        message = "Coverage line numbers must be positive and distinct."
        raise InvalidReportError(message)
    return result


def digest(path: Path) -> str:
    """Hash the exact bytes consumed by a test run or its report."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def input_paths(root: Path) -> list[Path]:
    """List application and measurement inputs, including unimported modules."""
    files = [
        path
        for directory in ("src", "tests", "scripts", "build-assets")
        for path in (root / directory).rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    ]
    files.extend(
        root / name
        for name in ("pyproject.toml", "uv.lock", ".python-version", "conftest.py")
        if (root / name).is_file()
    )
    return sorted(files)


def input_identity(root: Path) -> dict[str, str]:
    """Fingerprint source and test/configuration inputs without timestamps."""
    return {
        path.relative_to(root).as_posix(): digest(path) for path in input_paths(root)
    }


def validate_receipt(root: Path, report: Path, receipt: Path, data: Path) -> None:
    """Bind a successful test invocation to current inputs and exact report/data.

    This detects accidental stale/replaced evidence, not malicious forgery by a
    user who can rewrite both the report and receipt.
    """
    record = object_value(json.loads(receipt.read_text(encoding="utf-8")))
    if (
        integer(record["version"]) != RECEIPT_VERSION
        or integer(record["exitstatus"]) != 0
    ):
        message = "Coverage requires a successful contributing test run."
        raise InvalidReportError(message)
    if integer(record["tests_collected"]) == 0:
        message = "A collection-only or empty run cannot establish coverage."
        raise InvalidReportError(message)
    combination = object_value(record["combination"])
    if (
        record["invocation"] != "pytest"
        or combination["complete"] is not True
        or integer(combination["calls"]) == 0
        or integer(combination["completed"]) != integer(combination["calls"])
        or integer(combination["fragments"]) == 0
        or integer(combination["validated"]) != integer(combination["fragments"])
    ):
        message = "Coverage requires observed lossless measurement combination."
        raise InvalidReportError(message)
    if combinable_files(str(data)):
        message = "Coverage has uncombined parallel measurements beside selected data."
        raise InvalidReportError(message)
    started = integer(record["started_ns"])
    finished = integer(record["finished_ns"])
    if (
        not started <= report.stat().st_mtime_ns <= finished
        or not started <= data.stat().st_mtime_ns <= finished
    ):
        message = "Coverage report/data is stale or outside its recorded run."
        raise InvalidReportError(message)
    if record["inputs"] != input_identity(root):
        message = "Source, tests or measurement configuration changed after the run."
        raise InvalidReportError(message)
    if record["report_sha256"] != digest(report) or record["data_sha256"] != digest(
        data
    ):
        message = "Coverage report/data does not match the contributing run."
        raise InvalidReportError(message)


def validate_percentages(summary: dict[str, object]) -> None:
    """Reject invalid percentage metadata without using it as the line gate."""
    for name in (
        "percent_covered",
        "percent_statements_covered",
        "percent_branches_covered",
    ):
        for key in (name, name + "_display"):
            if key not in summary:
                continue
            value = summary[key]
            if isinstance(value, bool) or not isinstance(value, (float, int, str)):
                message = "Report percentages must be finite values between 0 and 100."
                raise InvalidReportError(message)
            percentage = float(value)
            if not math.isfinite(percentage) or not 0 <= percentage <= PERCENT_SCALE:
                message = "Report percentages must be finite values between 0 and 100."
                raise InvalidReportError(message)


def validate_counts(summary: dict[str, object], covered: int, statements: int) -> None:
    """Require self-consistent line and branch counts without a branch floor."""
    validate_percentages(summary)
    actual_covered = integer(summary["covered_lines"])
    actual_statements = integer(summary["num_statements"])
    missing = integer(summary["missing_lines"])
    branches = integer(summary["num_branches"])
    covered_branches = integer(summary["covered_branches"])
    missing_branches = integer(summary["missing_branches"])
    partial_branches = integer(summary["num_partial_branches"])
    if (
        actual_covered != covered
        or actual_statements != statements
        or covered + missing != statements
        or covered_branches + missing_branches != branches
        or partial_branches > missing_branches
        or integer(summary["excluded_lines"]) != 0
    ):
        message = "Coverage has impossible, inconsistent or excluded counts."
        raise InvalidReportError(message)


def application_counts(root: Path, report: Path) -> tuple[int, int]:
    """Check every source file and its executable denominator against Coverage.py."""
    document = object_value(json.loads(report.read_text(encoding="utf-8")))
    if object_value(document["meta"])["branch_coverage"] is not True:
        message = "Branch reporting must remain enabled."
        raise InvalidReportError(message)
    expected = {
        path.resolve() for path in (root / "src" / "batocera_gow").rglob("*.py")
    }
    files = object_value(document["files"])
    measured = {
        Path(name).resolve(): object_value(value) for name, value in files.items()
    }
    if not expected or measured.keys() != expected or len(measured) != len(files):
        message = "The report must include exactly every installed application module."
        raise InvalidReportError(message)
    analyzer = Coverage(config_file=False, branch=True, data_file=None)
    analyzer.set_option("report:exclude_lines", [])
    covered_total = 0
    statements_total = 0
    branch_totals = dict.fromkeys(
        (
            "num_branches",
            "covered_branches",
            "missing_branches",
            "num_partial_branches",
        ),
        0,
    )
    for path, value in measured.items():
        statements = set(analyzer.analysis2(str(path))[1])
        executed = line_numbers(value["executed_lines"])
        missing = line_numbers(value["missing_lines"])
        if (
            executed & missing
            or executed | missing != statements
            or value["excluded_lines"] != []
        ):
            message = (
                "Incomplete or changed executable denominator: "
                f"{path.relative_to(root)}"
            )
            raise InvalidReportError(message)
        validate_counts(object_value(value["summary"]), len(executed), len(statements))
        summary = object_value(value["summary"])
        for key in branch_totals:
            branch_totals[key] += integer(summary[key])
        covered_total += len(executed)
        statements_total += len(statements)
    validate_counts(object_value(document["totals"]), covered_total, statements_total)
    totals = object_value(document["totals"])
    if any(totals[key] != count for key, count in branch_totals.items()):
        message = "Branch totals do not match the measured application modules."
        raise InvalidReportError(message)
    if statements_total == 0:
        message = "Application source has no measured executable lines."
        raise InvalidReportError(message)
    return covered_total, statements_total


def main() -> int:
    """Return zero for the line floor, one below it, or two for invalid evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path("coverage.json"))
    parser.add_argument("--receipt", type=Path, default=Path("coverage-run.json"))
    parser.add_argument("--data", type=Path, default=Path(".coverage"))
    parser.add_argument(
        "--snapshot-inputs",
        action="store_true",
        help="Print receipt-adapter input identities, not a gate result.",
    )
    args = parser.parse_args()
    root = Path.cwd()
    if args.snapshot_inputs:
        sys.stdout.write(json.dumps(input_identity(root)) + "\n")
        return 0
    try:
        config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        minimum = float(config["tool"]["batocera-gow"]["coverage"]["minimum"])
        if not math.isfinite(minimum) or not MINIMUM_LINES <= minimum <= PERCENT_SCALE:
            message = (
                "The application line floor must be finite and between 80 and 100."
            )
            raise InvalidReportError(message)
        validate_receipt(root, args.report, args.receipt, args.data)
        covered, statements = application_counts(root, args.report)
    except (
        OSError,
        ValueError,
        OverflowError,
        TypeError,
        KeyError,
        CoverageException,
    ) as error:
        parser.error(str(error))
    sys.stdout.write(
        f"Application line coverage {covered / statements:.2%} "
        f"({covered}/{statements}); required {minimum:g}%. "
        "Branches reported separately.\n"
    )
    return int(covered * PERCENT_SCALE < minimum * statements)


if __name__ == "__main__":
    raise SystemExit(main())
