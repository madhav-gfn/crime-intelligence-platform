"""
Vendors a service's requirements.txt into backend/services/<name>/vendor/,
targeting Linux x86_64 CPython wheels regardless of the host OS this runs
on (developed on Windows; Zoho Catalyst AppSail's Managed Runtime containers
are Linux - /var/lang/bin/python3 in the crash logs is the giveaway).

Why this exists: Catalyst's Managed Runtime does not run `pip install` for
you - confirmed by a live deploy of auth-service failing with "No module
named uvicorn" even though requirements.txt lists it, and by Catalyst's own
Python AppSail docs, which say to manually install packages into the build
directory before upload. It doesn't matter whether you deploy by ZIP or via
the GitHub integration - neither runs a build step. So dependencies must be
pre-installed (vendored) into the uploaded directory before every deploy.

Vendored packages go into vendor/ (not the service root) so they don't get
mixed up with application code, and app-config.json sets PYTHONPATH=./vendor
so they're importable at runtime. vendor/ is gitignored - regenerate it
before every deploy the same way data/ is staged (see stage_service_data.py).
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES_DIR = REPO_ROOT / "backend" / "services"

# Must match each service's app-config.json "stack" (python3.13).
TARGET_PYTHON_VERSION = "313"
TARGET_IMPLEMENTATION = "cp"
TARGET_ABI = "cp313"
# Try a range of manylinux tags, oldest-compatible first, so pip can find a
# match even for packages that haven't published the newest tag yet.
TARGET_PLATFORMS = [
    "manylinux2014_x86_64",
    "manylinux_2_17_x86_64",
    "manylinux_2_28_x86_64",
    "linux_x86_64",
]

SERVICES = [
    "auth-service",
    "conversational-interface",
    "crime-forecasting",
    "explainable-ai",
    "financial-crime-analysis",
    "investigator-decision-support",
    "network-analysis",
    "offender-profiling",
    "pattern-analytics",
    "sociological-insights",
]


def vendor_service(service: str) -> None:
    service_dir = SERVICES_DIR / service
    requirements = service_dir / "requirements.txt"
    if not requirements.is_file():
        raise SystemExit(f"no requirements.txt at {requirements}")

    vendor_dir = service_dir / "vendor"
    if vendor_dir.exists():
        shutil.rmtree(vendor_dir)
    vendor_dir.mkdir(parents=True)

    cmd = [
        sys.executable, "-m", "pip", "install",
        "--implementation", TARGET_IMPLEMENTATION,
        "--python-version", TARGET_PYTHON_VERSION,
        "--abi", TARGET_ABI,
        "--only-binary=:all:",
        "--target", str(vendor_dir),
        "-r", str(requirements),
    ]
    for platform in TARGET_PLATFORMS:
        cmd += ["--platform", platform]

    print(f"vendoring {service} -> {vendor_dir}")
    subprocess.run(cmd, check=True)
    print(f"done: {service}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", nargs="?", default="all", choices=["all", *SERVICES])
    args = parser.parse_args()

    targets = SERVICES if args.service == "all" else [args.service]
    for service in targets:
        vendor_service(service)


if __name__ == "__main__":
    sys.exit(main())
