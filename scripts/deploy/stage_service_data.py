"""
Copies each service's required data subset out of the shared repo-root
data/ directory into that service's own backend/services/<name>/data/,
mirroring the same sub-path (e.g. data/seed -> <service>/data/seed).

Why this exists: Zoho Catalyst AppSail deploys one service directory at a
time (buildPath = backend/services/<name>) and only uploads files inside
that directory - it has no notion of the monorepo-wide data/ folder every
service's app/config.py defaults point at (repo_root/data/...). Rather
than change any application code, this script stages a self-contained copy
of just the files a given service actually reads, and each service's
app-config.json overrides its *_PATH/*_DIR env vars to point at the staged
./data/... copy instead of the default three-levels-up path. Local dev
(python -m uvicorn ..., no env override) is untouched.

Run after regenerating data/ via scripts/data_generation/ and before
`catalyst deploy appsail` for a given service.
"""

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
SERVICES_DIR = REPO_ROOT / "backend" / "services"

# Each entry: service directory name -> list of paths, relative to data/,
# to copy wholesale (directories are copied recursively; files copied as-is).
SERVICE_DATA_SOURCES: dict[str, list[str]] = {
    "auth-service": [
        "processed/auth",
    ],
    "conversational-interface": [
        "seed",
    ],
    "crime-forecasting": [
        "processed/forecasting",
    ],
    "explainable-ai": [
        "processed/explainability",
        "processed/offender-profiling",
        "seed",
    ],
    "financial-crime-analysis": [
        "processed/financial-crime",
    ],
    "investigator-decision-support": [
        "seed",
        "processed/offender-profiling",
        "processed/forecasting",
        "processed/sociology",
    ],
    "network-analysis": [
        "seed",
    ],
    "offender-profiling": [
        "processed/offender-profiling",
        "seed",
    ],
    "pattern-analytics": [
        "seed",
    ],
    "sociological-insights": [
        "processed/sociology",
    ],
}


def stage_service(service: str) -> None:
    sources = SERVICE_DATA_SOURCES[service]
    service_dir = SERVICES_DIR / service
    if not service_dir.is_dir():
        raise SystemExit(f"no such service directory: {service_dir}")

    dest_data_dir = service_dir / "data"
    if dest_data_dir.exists():
        shutil.rmtree(dest_data_dir)

    for rel in sources:
        src = DATA_DIR / rel
        dest = dest_data_dir / rel
        if not src.exists():
            raise SystemExit(
                f"{service}: expected source data at {src} but it doesn't exist - "
                f"run the relevant scripts/data_generation/ pipeline first"
            )
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)

    print(f"staged {service}: {', '.join(sources)} -> {dest_data_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "service",
        nargs="?",
        default="all",
        choices=["all", *SERVICE_DATA_SOURCES.keys()],
        help="service to stage, or 'all' (default)",
    )
    args = parser.parse_args()

    targets = list(SERVICE_DATA_SOURCES.keys()) if args.service == "all" else [args.service]
    for service in targets:
        stage_service(service)


if __name__ == "__main__":
    sys.exit(main())
