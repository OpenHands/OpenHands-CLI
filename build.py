#!/usr/bin/env python3
"""
Build script for OpenHands CLI using PyInstaller.

This script packages the OpenHands CLI into a standalone executable binary
using PyInstaller with the custom spec file.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


# =================================================
# SECTION: Build Binary
# =================================================


def clean_build_directories() -> None:
    """Clean up previous build artifacts."""
    print("🧹 Cleaning up previous build artifacts...")

    build_dirs = ["build", "dist", "__pycache__"]
    for dir_name in build_dirs:
        if os.path.exists(dir_name):
            print(f"  Removing {dir_name}/")
            shutil.rmtree(dir_name)

    # Clean up .pyc files
    for root, _dirs, files in os.walk("."):
        for file in files:
            if file.endswith(".pyc"):
                os.remove(os.path.join(root, file))

    print("✅ Cleanup complete!")


def check_pyinstaller() -> bool:
    """Check if PyInstaller is available."""
    try:
        subprocess.run(
            ["uv", "run", "pyinstaller", "--version"], check=True, capture_output=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(
            "❌ PyInstaller is not available. Use --install-pyinstaller flag or "
            "install manually with:"
        )
        print("   uv add --dev pyinstaller")
        return False


def build_executable(
    spec_file: str = "openhands-cli.spec",
    clean: bool = True,
) -> bool:
    """Build the executable using PyInstaller."""
    if clean:
        clean_build_directories()

    # Check if PyInstaller is available (installation is handled by build.sh)
    if not check_pyinstaller():
        return False

    print(f"🔨 Building executable using {spec_file}...")

    try:
        # Run PyInstaller with uv
        cmd = ["uv", "run", "pyinstaller", spec_file, "--clean"]

        print(f"Running: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, capture_output=True, text=True)

        print("✅ Build completed successfully!")

        # Check if the executable was created
        dist_dir = Path("dist")
        if dist_dir.exists():
            executables = list(dist_dir.glob("*"))
            if executables:
                print("📁 Executable(s) created in dist/:")
                for exe in executables:
                    size = exe.stat().st_size / (1024 * 1024)  # Size in MB
                    print(f"  - {exe.name} ({size:.1f} MB)")
            else:
                print("⚠️  No executables found in dist/ directory")

        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed: {e}")
        if e.stdout:
            print("STDOUT:", e.stdout)
        if e.stderr:
            print("STDERR:", e.stderr)
        return False


# =================================================
# SECTION: Test and profile binary
# =================================================


# =================================================
# SECTION: Main
# =================================================


def main() -> int:
    """Main function."""
    parser = argparse.ArgumentParser(description="Build OpenHands CLI executable")
    parser.add_argument(
        "--spec", default="openhands-cli.spec", help="PyInstaller spec file to use"
    )
    parser.add_argument(
        "--no-clean", action="store_true", help="Skip cleaning build directories"
    )
    parser.add_argument(
        "--no-test", action="store_true", help="Skip testing the built executable"
    )
    parser.add_argument(
        "--install-pyinstaller",
        action="store_true",
        help="Install PyInstaller using uv before building",
    )

    parser.add_argument(
        "--no-build", action="store_true", help="Skip building the executable"
    )

    args = parser.parse_args()

    print("🚀 OpenHands CLI Build Script")
    print("=" * 40)

    # Check if spec file exists
    if not os.path.exists(args.spec):
        print(f"❌ Spec file '{args.spec}' not found!")
        return 1

    # Build the executable
    if not args.no_build and not build_executable(args.spec, clean=not args.no_clean):
        return 1

    # Test the executable
    if not args.no_test:
        from e2e_tests.runner import print_detailed_results, run_all_e2e_tests

        summary = run_all_e2e_tests()
        print_detailed_results(summary)

        if not summary.all_passed:
            print(f"\n❌ {summary.failed_tests} test(s) failed, build process failed")
            return 1

    print("\n🎉 Build process completed!")
    print("📁 Check the 'dist/' directory for your executable")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(e)
        print("❌ Executable test failed")
        sys.exit(1)
