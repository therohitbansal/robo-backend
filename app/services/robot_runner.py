import os
import subprocess
from typing import Dict, List, Optional


def run_robot_suite(
    suite_path: str,
    output_dir: str,
    variables: Optional[Dict[str, str]] = None,
    extra_args: Optional[List[str]] = None,
) -> int:
    os.makedirs(output_dir, exist_ok=True)
    cmd = [
        "robot",
        "-d",
        output_dir,
        "--listener",
        "allure_robotframework",  # writes allure-results if plugin installed
    ]
    if variables:
        for k, v in variables.items():
            cmd.extend(["-v", f"{k}:{v}"])
    if extra_args:
        cmd.extend(extra_args)
    cmd.append(suite_path)

    work_dir = os.path.dirname(os.path.abspath(suite_path)) or None
    env = os.environ.copy()
    # Tell allure-robotframework where to place results
    env["ALLURE_RESULTS_DIR"] = os.path.join(output_dir, "allure-results")
    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=work_dir,  # run from suite directory so relative resources work
        env=env,
    )  # noqa: S603, S607
    with open(os.path.join(output_dir, "stdout.txt"), "w", encoding="utf-8") as f:
        f.write(completed.stdout)
    with open(os.path.join(output_dir, "stderr.txt"), "w", encoding="utf-8") as f:
        f.write(completed.stderr)

    # Try generating static Allure report if 'allure' CLI is available
    try:
        results_dir = os.path.join(output_dir, "allure-results")
        report_dir = os.path.join(output_dir, "allure-report")
        if os.path.isdir(results_dir):
            subprocess.run(["allure", "generate", results_dir, "-o", report_dir, "--clean"], check=False)  # noqa: S603
    except Exception:
        pass
    return completed.returncode

