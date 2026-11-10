"""Exercise the independent line gate with real Coverage.py consumer reports."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CHECKER = ROOT / "scripts" / "check_python_coverage.py"


def consumer_project(tmp_path: Path) -> None:
    """Install the real measurement adapter beside an owned tiny application."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copyfile(CHECKER, scripts / CHECKER.name)
    shutil.copyfile(ROOT / "conftest.py", tmp_path / "conftest.py")
    source = tmp_path / "src" / "batocera_gow"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text("", encoding="utf-8")
    (source / "application.py").write_text(
        "flag = globals().get('flag', True)\n"
        "if flag:\n"
        "    value = 1\n"
        "else:\n"
        "    value = 2\n"
        "result = value + 1\n",
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\n"
        'addopts = ["--cov", "--cov-report=json:coverage.json"]\n'
        '[tool.coverage.run]\nbranch = true\nsource = ["src/batocera_gow"]\n'
        'patch = ["subprocess"]\nrelative_files = true\n'
        "[tool.coverage.report]\nexclude_lines = []\n"
        "[tool.batocera-gow.coverage]\nminimum = 80\n",
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_consumer.py").write_text(
        "import runpy\n"
        "def test_result():\n"
        '    result = runpy.run_path("src/batocera_gow/application.py")["result"]\n'
        "    assert result == 2\n",
        encoding="utf-8",
    )


def run_consumer(
    tmp_path: Path, *args: str, console: bool = False
) -> subprocess.CompletedProcess[str]:
    """Execute private pytest without inherited measurement or pytest options."""
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("COVERAGE_", "COV_CORE_", "PYTEST_"))
    }
    selected = next(
        (
            arg.removeprefix("--coverage-evidence-dir=")
            for arg in args
            if arg.startswith("--coverage-evidence-dir=")
        ),
        None,
    )
    if "--coverage-evidence-dir" in args:
        selected = args[args.index("--coverage-evidence-dir") + 1]
    if selected is not None:
        environment["COVERAGE_FILE"] = str(Path(selected) / ".coverage")
    runner = (
        [str(Path(sys.executable).with_name("pytest"))]
        if console
        else [sys.executable, "-m", "pytest"]
    )
    return subprocess.run(  # noqa: S603  # Fixed interpreter and owned synthetic project.
        [*runner, "-q", *args],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def measure(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    """Obtain canonical receipts from real pytest, never manufacture completeness."""
    consumer_project(tmp_path)
    result = run_consumer(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = json.loads((tmp_path / "coverage-run.json").read_text(encoding="utf-8"))
    assert isinstance(receipt, dict)
    return tmp_path / "coverage.json", receipt


def gate(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Invoke the real standalone checker without a shell or inherited coverage."""
    return subprocess.run(  # noqa: S603  # Repository-owned CLI and synthetic paths only.
        [sys.executable, str(CHECKER), *args],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )


def test_sufficient_lines_pass_independently_of_uncovered_branch(
    tmp_path: Path,
) -> None:
    """Four of five statements pass 80% despite an unexecuted else decision."""
    measure(tmp_path)
    evidence = [
        tmp_path / name for name in (".coverage", "coverage.json", "coverage-run.json")
    ]
    original = {
        path: hashlib.sha256(path.read_bytes()).hexdigest() for path in evidence
    }
    result = gate(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "80.00%" in result.stdout
    assert {
        path: hashlib.sha256(path.read_bytes()).hexdigest() for path in evidence
    } == original
    repeated = gate(tmp_path)
    assert repeated.returncode == 0, repeated.stderr
    assert {
        path: hashlib.sha256(path.read_bytes()).hexdigest() for path in evidence
    } == original


def test_missing_measurement_is_invalid_not_below_floor(tmp_path: Path) -> None:
    """Missing reports must not produce a no-application success."""
    result = gate(tmp_path)
    assert result.returncode == 2


def reseal(tmp_path: Path, receipt: dict[str, object]) -> None:
    """Keep fixture provenance valid while independently corrupting report fields."""
    report = tmp_path / "coverage.json"
    receipt["report_sha256"] = hashlib.sha256(report.read_bytes()).hexdigest()
    receipt["finished_ns"] = time.time_ns()
    (tmp_path / "coverage-run.json").write_text(json.dumps(receipt), encoding="utf-8")


def test_failed_floor_is_distinct_from_invalid_measurement(tmp_path: Path) -> None:
    """A valid 80% line result fails a higher configured floor with status one."""
    report, receipt = measure(tmp_path)
    config = tmp_path / "pyproject.toml"
    config.write_text("[tool.batocera-gow.coverage]\nminimum = 90\n", encoding="utf-8")
    document = json.loads(report.read_text(encoding="utf-8"))
    document["totals"]["percent_covered"] = 100
    report.write_text(json.dumps(document), encoding="utf-8")
    inputs = receipt["inputs"]
    assert isinstance(inputs, dict)
    inputs["pyproject.toml"] = hashlib.sha256(config.read_bytes()).hexdigest()
    reseal(tmp_path, receipt)
    result = gate(tmp_path)
    assert result.returncode == 1, result.stderr
    assert "80.00%" in result.stdout


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("num_statements", True),
        ("num_statements", 5.5),
        ("covered_lines", -1),
        ("covered_lines", 6),
        ("covered_lines", 3),
        ("covered_branches", 100),
    ],
)
def test_impossible_counts_are_invalid_not_floor_failures(
    tmp_path: Path,
    field: str,
    value: float,
) -> None:
    """Reject malformed or inconsistent counts even with a valid receipt hash."""
    report, receipt = measure(tmp_path)
    document = json.loads(report.read_text(encoding="utf-8"))
    document["totals"][field] = value
    report.write_text(json.dumps(document), encoding="utf-8")
    reseal(tmp_path, receipt)
    assert gate(tmp_path).returncode == 2


@pytest.mark.parametrize(
    "corruption",
    [
        "missing-totals",
        "missing-module",
        "foreign-module",
        "missing-statement",
        "overlapping-lines",
        "duplicated-line",
        "excluded-line",
        "branches-disabled",
    ],
)
def test_invalid_complete_measurement_is_not_a_floor_failure(
    tmp_path: Path,
    corruption: str,
) -> None:
    """Reject semantic corruption even when report hashes match the run receipt."""
    report, receipt = measure(tmp_path)
    document = json.loads(report.read_text(encoding="utf-8"))
    application = next(
        name for name in document["files"] if name.endswith("application.py")
    )
    entry = document["files"][application]
    match corruption:
        case "missing-totals":
            del document["totals"]
        case "missing-module":
            del document["files"][
                next(name for name in document["files"] if name.endswith("__init__.py"))
            ]
        case "foreign-module":
            document["files"]["tests/tooling.py"] = entry
        case "missing-statement":
            entry["missing_lines"] = []
        case "overlapping-lines":
            entry["missing_lines"] = [1, 5]
        case "duplicated-line":
            entry["executed_lines"].append(1)
        case "excluded-line":
            entry["excluded_lines"] = [5]
        case "branches-disabled":
            document["meta"]["branch_coverage"] = False
    report.write_text(json.dumps(document), encoding="utf-8")
    reseal(tmp_path, receipt)
    assert gate(tmp_path).returncode == 2


@pytest.mark.parametrize("minimum", ["nan", "inf", "-inf", "79", "101"])
def test_invalid_floor_cannot_pass(tmp_path: Path, minimum: str) -> None:
    """Reject nonfinite, weakened or impossible policy thresholds."""
    measure(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        f"[tool.batocera-gow.coverage]\nminimum = {minimum}\n",
        encoding="utf-8",
    )
    assert gate(tmp_path).returncode == 2


@pytest.mark.parametrize(
    "changed", ["source", "configuration", "report", "data", "receipt"]
)
def test_changed_evidence_or_inputs_is_stale(tmp_path: Path, changed: str) -> None:
    """A previously passing report cannot endorse changed source or evidence."""
    measure(tmp_path)
    paths = {
        "source": tmp_path / "src" / "batocera_gow" / "application.py",
        "configuration": tmp_path / "pyproject.toml",
        "report": tmp_path / "coverage.json",
        "data": tmp_path / ".coverage",
        "receipt": tmp_path / "coverage-run.json",
    }
    path = paths[changed]
    if changed == "receipt":
        path.unlink()
    else:
        path.write_bytes(path.read_bytes() + b"\n")
    assert gate(tmp_path).returncode == 2


@pytest.mark.parametrize("filename", ["coverage.json", ".coverage"])
def test_preexisting_measurement_is_not_fresh(tmp_path: Path, filename: str) -> None:
    """Matching content hashes do not make data from before the run current."""
    _, receipt = measure(tmp_path)
    started = receipt["started_ns"]
    assert isinstance(started, int)
    os.utime(tmp_path / filename, ns=(started - 1_000_000_000, started - 1_000_000_000))
    assert gate(tmp_path).returncode == 2


@pytest.mark.parametrize(
    ("field", "value"), [("exitstatus", 1), ("tests_collected", 0)]
)
def test_failed_or_empty_contributor_is_not_evidence(
    tmp_path: Path,
    field: str,
    value: int,
) -> None:
    """A report left by failed tests or collection cannot establish acceptance."""
    _, receipt = measure(tmp_path)
    receipt[field] = value
    reseal(tmp_path, receipt)
    assert gate(tmp_path).returncode == 2


def test_new_unexecuted_module_invalidates_previous_denominator(tmp_path: Path) -> None:
    """Adding source cannot preserve a passing import-selected report."""
    _, receipt = measure(tmp_path)
    path = tmp_path / "src" / "batocera_gow" / "unexecuted.py"
    path.write_text("unexecuted = 1\n", encoding="utf-8")
    inputs = receipt["inputs"]
    assert isinstance(inputs, dict)
    inputs["src/batocera_gow/unexecuted.py"] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    reseal(tmp_path, receipt)
    assert gate(tmp_path).returncode == 2


def test_empty_application_cannot_inherit_template_not_applicable(
    tmp_path: Path,
) -> None:
    """Even a receipt matching an empty tree cannot waive the application."""
    _, receipt = measure(tmp_path)
    for path in (tmp_path / "src").rglob("*.py"):
        path.unlink()
    inputs = receipt["inputs"]
    assert isinstance(inputs, dict)
    receipt["inputs"] = {
        name: value for name, value in inputs.items() if not name.startswith("src/")
    }
    reseal(tmp_path, receipt)
    assert gate(tmp_path).returncode == 2


@pytest.mark.parametrize("contents", ["{", "null", "[]", '{"totals": null}'])
def test_malformed_json_report_is_invalid(tmp_path: Path, contents: str) -> None:
    """Malformed JSON and wrong root shapes are invalid evidence, not a crash."""
    report, receipt = measure(tmp_path)
    report.write_text(contents, encoding="utf-8")
    reseal(tmp_path, receipt)
    assert gate(tmp_path).returncode == 2


def test_pytest_adapter_invalidates_failed_and_collection_only_runs(
    tmp_path: Path,
) -> None:
    """Exercise actual successful, failed and collection-only receipt transitions."""
    consumer_project(tmp_path)
    consumer = tmp_path / "tests/test_consumer.py"
    success = run_consumer(tmp_path)
    assert success.returncode == 0, success.stdout + success.stderr
    assert gate(tmp_path).returncode == 0
    appended = run_consumer(tmp_path, "--cov-append")
    assert appended.returncode == 0, appended.stdout + appended.stderr
    assert not (tmp_path / "coverage-run.json").exists()
    assert gate(tmp_path).returncode == 2
    collection = run_consumer(tmp_path, "--collect-only")
    assert collection.returncode == 0
    assert not (tmp_path / "coverage-run.json").exists()
    assert gate(tmp_path).returncode == 2
    consumer.write_text("def test_result():\n    assert False\n", encoding="utf-8")
    failure = run_consumer(tmp_path)
    assert failure.returncode == 1
    assert not (tmp_path / "coverage-run.json").exists()
    assert gate(tmp_path).returncode == 2


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("percent_covered", float("nan")),
        ("percent_statements_covered", float("inf")),
        ("percent_branches_covered", -1),
        ("percent_covered_display", "nan"),
    ],
)
def test_nonfinite_or_impossible_report_percentage_is_invalid(
    tmp_path: Path,
    field: str,
    value: float | str,
) -> None:
    """Nonauthoritative combined/display values still must be valid measurements."""
    report, receipt = measure(tmp_path)
    document = json.loads(report.read_text(encoding="utf-8"))
    document["totals"][field] = value
    report.write_text(json.dumps(document), encoding="utf-8")
    reseal(tmp_path, receipt)
    assert gate(tmp_path).returncode == 2


@pytest.mark.parametrize("location", ["totals", "module", "threshold"])
def test_oversized_integer_is_invalid_evidence_not_floor_failure(
    tmp_path: Path,
    location: str,
) -> None:
    """Numeric conversion overflow must remain a controlled invalid-report error."""
    report, receipt = measure(tmp_path)
    oversized = 10**400
    if location == "threshold":
        (tmp_path / "pyproject.toml").write_text(
            f"[tool.batocera-gow.coverage]\nminimum = {oversized}\n",
            encoding="utf-8",
        )
    else:
        document = json.loads(report.read_text(encoding="utf-8"))
        summary = document["totals"]
        if location == "module":
            application = next(
                name for name in document["files"] if name.endswith("application.py")
            )
            summary = document["files"][application]["summary"]
        summary["percent_covered"] = oversized
        report.write_text(json.dumps(document), encoding="utf-8")
        reseal(tmp_path, receipt)
    result = gate(tmp_path)
    assert result.returncode == 2, result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("fragment", ["missing-schema", "truncated", "empty"])
def test_lost_fragment_invalidates_sufficient_numerical_measurement(
    tmp_path: Path, fragment: str
) -> None:
    """Real combine loss cannot authorize an otherwise sufficient 100% report."""
    consumer_project(tmp_path)
    (tmp_path / "src/batocera_gow/application.py").write_text(
        "result = 2\n", encoding="utf-8"
    )
    consumer = tmp_path / "tests/test_consumer.py"
    damage = (
        "    with sqlite3.connect(data.data_filename()) as connection:\n"
        "        connection.execute('DELETE FROM coverage_schema')\n"
        if fragment == "missing-schema"
        else "    from pathlib import Path\n"
        "    Path(data.data_filename()).write_bytes(b'truncated')\n"
    )
    if fragment == "empty":
        damage = (
            "    from pathlib import Path\n"
            "    Path(data.data_filename()).write_bytes(b'')\n"
        )
    consumer.write_text(
        consumer.read_text(encoding="utf-8") + "\ndef test_contribution():\n"
        "    from coverage import Coverage, CoverageData\n"
        "    from pathlib import Path\n"
        "    measurement = Coverage.current()\n"
        "    assert measurement is not None\n"
        "    measurement.json_report(outfile='coverage.json')\n"
        "    import sqlite3\n"
        "    data = CoverageData('.coverage.contribution')\n"
        "    data.add_arcs({'src/batocera_gow/application.py': []})\n"
        "    data.write()\n"
        + damage
        + "    before = Path(data.data_filename()).read_bytes()\n"
        "    Path('fragment-before').write_bytes(before)\n",
        encoding="utf-8",
    )
    result = run_consumer(tmp_path)
    report = json.loads((tmp_path / "coverage.json").read_text(encoding="utf-8"))
    assert report["totals"]["covered_lines"] == 1
    assert report["totals"]["num_statements"] == 1
    assert result.returncode != 0
    assert not (tmp_path / "coverage-run.json").exists()
    assert gate(tmp_path).returncode == 2
    assert (tmp_path / ".coverage.contribution").read_bytes() == (
        tmp_path / "fragment-before"
    ).read_bytes()


def test_valid_zero_execution_fragment_and_unimported_module_are_complete(
    tmp_path: Path,
) -> None:
    """Schema-valid zero-execution data is not loss; unimported source still counts."""
    consumer_project(tmp_path)
    (tmp_path / "src/batocera_gow/application.py").write_text(
        "first = 1\nsecond = 2\nthird = 3\nfourth = 4\nresult = 2\n",
        encoding="utf-8",
    )
    (tmp_path / "src/batocera_gow/unimported.py").write_text(
        "unimported = 1\n", encoding="utf-8"
    )
    consumer = tmp_path / "tests/test_consumer.py"
    consumer.write_text(
        consumer.read_text(encoding="utf-8") + "\ndef test_zero_contribution():\n"
        "    from coverage import CoverageData\n"
        "    data = CoverageData('.coverage.zero')\n"
        "    data.add_arcs({'src/batocera_gow/unimported.py': []})\n"
        "    data.write()\n",
        encoding="utf-8",
    )
    result = run_consumer(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    record = json.loads((tmp_path / "coverage-run.json").read_text(encoding="utf-8"))
    assert record["combination"]["fragments"] >= 2
    assert record["combination"]["fragments"] == record["combination"]["validated"]
    assert gate(tmp_path).returncode == 0
    report = json.loads((tmp_path / "coverage.json").read_text(encoding="utf-8"))
    assert report["files"]["src/batocera_gow/unimported.py"]["executed_lines"] == []
    assert report["totals"]["covered_lines"] == 5
    assert report["totals"]["num_statements"] == 6


def test_private_measurement_preserves_root_history_and_binds_exact_outputs(
    tmp_path: Path,
) -> None:
    """Private pytest and the independent CLI never consume root historical shards."""
    consumer_project(tmp_path)
    history = {
        ".coverage": b"historical combined data",
        ".coverage.history": b"historical shard",
        "coverage.json": b"historical report",
        "coverage-run.json": b"historical receipt",
    }
    for name, value in history.items():
        (tmp_path / name).write_bytes(value)
    private = tmp_path / "private-evidence"
    private.mkdir(mode=0o700)
    result = run_consumer(
        tmp_path,
        "--coverage-evidence-dir",
        str(private),
        f"--cov-report=json:{private / 'coverage.json'}",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    args = [
        sys.executable,
        str(CHECKER),
        "--report",
        str(private / "coverage.json"),
        "--receipt",
        str(private / "coverage-run.json"),
        "--data",
        str(private / ".coverage"),
    ]
    accepted = subprocess.run(  # noqa: S603  # Actual checker with owned fixture paths.
        args, cwd=tmp_path, capture_output=True, text=True, check=False, timeout=10
    )
    assert accepted.returncode == 0, accepted.stderr
    receipt = (private / "coverage-run.json").read_text(encoding="utf-8")
    assert str(tmp_path) not in receipt
    assert '"command"' not in receipt
    assert (private / "coverage-run.json").stat().st_mode & 0o777 == 0o600
    (private / ".coverage").write_bytes(b"mismatched measurement")
    refused = subprocess.run(  # noqa: S603  # Same checker refuses replaced measurement.
        args, cwd=tmp_path, capture_output=True, text=True, check=False, timeout=10
    )
    assert refused.returncode == 2
    assert {name: (tmp_path / name).read_bytes() for name in history} == history


@pytest.mark.parametrize(
    "corruption", ["missing", "count", "lost", "version", "unfinished"]
)
def test_incomplete_or_legacy_combination_receipt_is_invalid(
    tmp_path: Path, corruption: str
) -> None:
    """The independent CLI requires observed, reconciled combination evidence."""
    _, receipt = measure(tmp_path)
    combination = receipt["combination"]
    assert isinstance(combination, dict)
    if corruption == "missing":
        del receipt["combination"]
    elif corruption == "count":
        combination["validated"] = 0
    elif corruption == "lost":
        combination["complete"] = False
    elif corruption == "unfinished":
        combination["completed"] = 0
    else:
        receipt["version"] = 1
    reseal(tmp_path, receipt)
    assert gate(tmp_path).returncode == 2


def test_late_uncombined_contribution_cannot_publish_success(tmp_path: Path) -> None:
    """A real fragment arriving after pytest-cov finishes is incomplete evidence."""
    consumer_project(tmp_path)
    (tmp_path / "src/batocera_gow/application.py").write_text(
        "result = 2\n", encoding="utf-8"
    )
    (tmp_path / "late_contribution.py").write_text(
        "from coverage import CoverageData\n"
        "def pytest_sessionfinish(session):\n"
        "    data = CoverageData('.coverage.late')\n"
        "    data.add_arcs({'src/batocera_gow/application.py': [(1, 2)]})\n"
        "    data.write()\n",
        encoding="utf-8",
    )
    result = run_consumer(tmp_path, "-p", "late_contribution")
    assert result.returncode == 2
    report = json.loads((tmp_path / "coverage.json").read_text(encoding="utf-8"))
    assert report["totals"]["covered_lines"] == 1
    assert report["totals"]["num_statements"] == 1
    assert not (tmp_path / "coverage-run.json").exists()
    assert gate(tmp_path).returncode == 2


def test_console_pytest_importlib_produces_complete_receipt(tmp_path: Path) -> None:
    """The documented console runner works without adding tooling to sys.path."""
    consumer_project(tmp_path)
    result = run_consumer(tmp_path, "--import-mode=importlib", console=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert gate(tmp_path).returncode == 0


@pytest.mark.parametrize("console", [False, True])
def test_existing_external_directory_accepts_canonical_attached_option(
    tmp_path: Path, *, console: bool
) -> None:
    """An external evidence path must not become pytest's initial discovery root."""
    project = tmp_path / "checkout"
    project.mkdir()
    consumer_project(project)
    evidence = tmp_path / "existing-private-evidence"
    evidence.mkdir(mode=0o700)
    result = run_consumer(
        project,
        "--import-mode=importlib",
        f"--coverage-evidence-dir={evidence}",
        f"--cov-report=json:{evidence / 'coverage.json'}",
        console=console,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    accepted = gate(
        project,
        "--report",
        str(evidence / "coverage.json"),
        "--receipt",
        str(evidence / "coverage-run.json"),
        "--data",
        str(evidence / ".coverage"),
    )
    assert accepted.returncode == 0, accepted.stderr
    for name in (".coverage", "coverage.json", "coverage-run.json"):
        assert (evidence / name).is_file()
        assert not (project / name).exists()


def test_fragment_arriving_inside_real_combine_is_never_consumed(
    tmp_path: Path,
) -> None:
    """A second Coverage enumeration cannot initialize and delete unaudited bytes."""
    consumer_project(tmp_path)
    (tmp_path / "arriving_contribution.py").write_text(
        "from pathlib import Path\n"
        "import coverage.data\n"
        "original = coverage.data.combinable_files\n"
        "def arriving(data_file, data_paths=None):\n"
        "    Path('.coverage.arriving').write_bytes(b'')\n"
        "    return original(data_file, data_paths)\n"
        "def pytest_runtestloop(session):\n"
        "    coverage.data.combinable_files = arriving\n",
        encoding="utf-8",
    )
    result = run_consumer(tmp_path, "-p", "arriving_contribution")
    assert (tmp_path / "coverage.json").is_file()
    assert result.returncode != 0, result.stdout + result.stderr
    assert not (tmp_path / "coverage-run.json").exists()
    assert gate(tmp_path).returncode == 2
    assert (tmp_path / ".coverage.arriving").read_bytes() == b""


def test_original_fragment_changed_after_audit_is_preserved_and_refused(
    tmp_path: Path,
) -> None:
    """Combining frozen bytes cannot authorize a changed original contribution."""
    consumer_project(tmp_path)
    consumer = tmp_path / "tests/test_consumer.py"
    consumer.write_text(
        consumer.read_text(encoding="utf-8") + "\ndef test_contribution():\n"
        "    from coverage import CoverageData\n"
        "    data = CoverageData('.coverage.changing')\n"
        "    data.add_arcs({'src/batocera_gow/application.py': []})\n"
        "    data.write()\n",
        encoding="utf-8",
    )
    (tmp_path / "changing_contribution.py").write_text(
        "from pathlib import Path\n"
        "import coverage.data\n"
        "original = coverage.data.combinable_files\n"
        "def changing(data_file, data_paths=None):\n"
        "    Path('.coverage.changing').write_bytes(b'')\n"
        "    return original(data_file, data_paths)\n"
        "def pytest_runtestloop(session):\n"
        "    coverage.data.combinable_files = changing\n",
        encoding="utf-8",
    )
    result = run_consumer(tmp_path, "-p", "changing_contribution")
    assert (tmp_path / "coverage.json").is_file()
    assert result.returncode != 0, result.stdout + result.stderr
    assert not (tmp_path / "coverage-run.json").exists()
    assert gate(tmp_path).returncode == 2
    assert (tmp_path / ".coverage.changing").read_bytes() == b""


@pytest.mark.parametrize("private", [False, True])
def test_instrumented_child_after_receipt_invalidates_selected_measurement(
    tmp_path: Path, *, private: bool
) -> None:
    """The independent gate must detect real shards written after publication."""
    project = tmp_path / "checkout"
    project.mkdir()
    consumer_project(project)
    evidence = tmp_path / "private-evidence" if private else project
    options = (
        [
            f"--coverage-evidence-dir={evidence}",
            f"--cov-report=json:{evidence / 'coverage.json'}",
        ]
        if private
        else []
    )
    result = run_consumer(project, *options)
    assert result.returncode == 0, result.stdout + result.stderr
    arguments = [
        "--report",
        str(evidence / "coverage.json"),
        "--receipt",
        str(evidence / "coverage-run.json"),
        "--data",
        str(evidence / ".coverage"),
    ]
    assert gate(project, *arguments).returncode == 0
    artifacts = {
        name: (evidence / name).read_bytes()
        for name in (".coverage", "coverage.json", "coverage-run.json")
    }
    child = subprocess.run(  # noqa: S603  # Real instrumented owned application child.
        [
            sys.executable,
            "-m",
            "coverage",
            "run",
            "--parallel-mode",
            f"--data-file={evidence / '.coverage'}",
            "src/batocera_gow/application.py",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert child.returncode == 0, child.stdout + child.stderr
    assert list(evidence.glob(".coverage.*"))
    assert {name: (evidence / name).read_bytes() for name in artifacts} == artifacts
    refused = gate(project, *arguments) if private else gate(project)
    assert refused.returncode == 2, refused.stdout + refused.stderr
