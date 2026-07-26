"""
Builds a Zoho Catalyst AppSail deploy zip for one service, with app/,
data/, vendor/, app-config.json, and requirements.txt sitting directly at
the zip root (not nested inside a <service>/ folder) - the Console's
"Create Deployment" upload expects the build directory's own contents at
the archive root, not the directory itself.

Run scripts/deploy/stage_service_data.py and vendor_service_deps.py for the
service first - this script only packages what's already on disk.
"""

import argparse
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES_DIR = REPO_ROOT / "backend" / "services"
OUT_DIR = Path(__file__).resolve().parent

INCLUDE = ["app", "data", "vendor", "app-config.json", "requirements.txt"]


def build_zip(service: str) -> Path:
    service_dir = SERVICES_DIR / service
    if not service_dir.is_dir():
        raise SystemExit(f"no such service directory: {service_dir}")

    missing = [item for item in INCLUDE if not (service_dir / item).exists()]
    if missing:
        raise SystemExit(
            f"{service}: missing {missing} - run stage_service_data.py and "
            f"vendor_service_deps.py for this service first"
        )

    out_path = OUT_DIR / f"{service}-deploy.zip"
    if out_path.exists():
        out_path.unlink()

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for item in INCLUDE:
            src = service_dir / item
            if src.is_dir():
                for path in src.rglob("*"):
                    if "__pycache__" in path.parts or not path.is_file():
                        continue
                    z.write(path, path.relative_to(service_dir))
            else:
                z.write(src, item)

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"{service}: {out_path} ({size_mb:.1f} MB)")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", nargs="?", default="all")
    args = parser.parse_args()

    if args.service == "all":
        targets = sorted(d.name for d in SERVICES_DIR.iterdir() if (d / "app-config.json").exists())
    else:
        targets = [args.service]

    for service in targets:
        build_zip(service)


if __name__ == "__main__":
    sys.exit(main())
