"""Write evidence to the Actions summary without inventing missing results."""

import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


artifacts = Path("artifacts")
artifacts.mkdir(exist_ok=True)
kind = sys.argv[1]
if kind == "tests":
    path = artifacts / "pytest.xml"
    if path.exists():
        suites = ET.parse(path).getroot().iter("testsuite")
        counts = {key: 0 for key in ("tests", "failures", "errors", "skipped")}
        for suite in suites:
            for key in counts:
                counts[key] += int(suite.get(key, "0"))
        counts["passed"] = counts["tests"] - counts["failures"] - counts["errors"] - counts["skipped"]
        (artifacts / "python-results.json").write_text(json.dumps(counts, indent=2) + "\n", encoding="utf-8")
        summary = f"## Python tests\n\n{counts['passed']}/{counts['tests']} passed, {counts['failures']} failures, {counts['errors']} errors, {counts['skipped']} skipped.\n\nTypeScript test output and API request logs are in the test-results artifact.\n"
    else:
        summary = "## Tests\n\nNo pytest report was produced. Inspect the failed setup/test step.\n"
else:
    path = artifacts / "smoke.json"
    if path.exists():
        report = json.loads(path.read_text(encoding="utf-8"))
        summary = f"## Kubernetes proxy smoke\n\n{report['passed']}/{len(report['checks'])} checks passed, {report['failed']} failed.\n\n"
        summary += "| Check | Result | Detail |\n| --- | --- | --- |\n"
        for check in report["checks"]:
            detail = json.dumps(check["detail"]).replace("|", "\\|")
            summary += f"| {check['check']} | {'pass' if check['passed'] else 'FAIL'} | `{detail}` |\n"
    else:
        summary = "## Kubernetes proxy smoke\n\nNo smoke report was produced. Inspect deployment diagnostics in the kind-smoke-logs artifact.\n"
summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
if summary_path:
    with open(summary_path, "a", encoding="utf-8") as output:
        output.write(summary)
print(summary)
