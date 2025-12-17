#!/usr/bin/env python3
from __future__ import annotations

import base64
from dataclasses import dataclass
import os
import subprocess
import sys
import time
import glob
from typing import Dict
from typing import List
from typing import Optional
from typing import Sequence

import requests


# TODO: replace me to dd-trace-py ops' slack channel once initial onboarding is done
SLACK_CHANNEL = "fuzzing-ops"
TEAM_NAME = "profiling-python"
REPOSITORY_URL = "https://github.com/DataDog/dd-trace-py"
PROJECT_NAME = "dd-trace-py"
# We currently only support libfuzzer for this repository.
FUZZ_TYPE = "libfuzzer"

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

FUZZER_BINARY_BASE_PATH = "/tmp/fuzz/build"

API_URL = "https://fuzzing-api.us1.ddbuild.io/api/v1"
MAX_PKG_NAME_LENGTH = 50
VAULT_PATH = "vault"

@dataclass(frozen=True)
class FuzzProject:
    pkgname: str
    binary_name: str
    binary_path: str
    fuzz_dir: str
    build_script: str

def build_and_upload_fuzz(team: str = TEAM_NAME) -> None:
    """
    This builds and uploads fuzz targets to the internal fuzzing infrastructure.
    It needs to be passed the -fuzz flag in order to build the fuzz with efficient coverage guidance.
    """

    git_sha = os.popen("git rev-parse HEAD").read().strip()

    projects = discover_fuzz_projects(REPO_ROOT)
    if not projects:
        print(f"❌ No fuzz projects found under {REPO_ROOT}")
        return

    for project in projects:
        build(project)
        upload_binary(project.pkgname, project.binary_name, project.binary_relpath, git_sha)
        create_fuzzer(project.pkgname, project.binary_name, git_sha)
    print("✅ Fuzzing infrastructure setup completed successfully!")

def get_package_name(binary):
    name = os.path.basename(binary)
    return PROJECT_NAME + "-" + name[:MAX_PKG_NAME_LENGTH].replace("_", "-")


def _is_executable(file_path: str) -> bool:
    return os.path.isfile(file_path) and os.access(file_path, os.X_OK)


def discover_fuzz_projects(repo_root: str) -> List[FuzzProject]:
    """
    Discover fuzz projects by looking for '**/fuzz/build.sh'

    This allows for "0 click onboarding" for new fuzz harnesses.
    """
    projects: List[FuzzProject] = []
    for build_script in glob.glob(os.path.join(repo_root, "**/fuzz/build.sh"), recursive=True):
        print(f"Found build script: {build_script}")
        fuzz_dir = os.path.dirname(build_script)
        projects.append(
            FuzzProject(
                pkgname=get_package_name(build_script),
                binary_name=os.path.basename(build_script),
                binary_path=os.path.join(FUZZER_BINARY_BASE_PATH, os.path.basename(build_script)),
                fuzz_dir=fuzz_dir,
                build_script=build_script,
            )
        )
    return projects

def build(project: FuzzProject) -> None:
    print(f"Building fuzz directory: {project.fuzz_dir}")
    if not os.path.isfile(project.build_script):
        raise FileNotFoundError(project.build_script)
    # Run with bash to avoid relying on executable bit.
    result = subprocess.run([project.build_script], cwd=project.fuzz_dir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    print("✅ Built all fuzzers")

def create_fuzzer(pkgname: str, binary: str, git_sha: str, team: str, slack_channel: str, repository_url: str) -> bool:
    print(f"Starting fuzzer for {pkgname} ({binary})...")
    # Start new fuzzer
    run_payload = {
        "app": pkgname,
        "debug": False,
        "version": git_sha,
        "type": FUZZ_TYPE,
        "binary": binary,
        "team": team,
        "slack_channel": slack_channel,
        "repository_url": repository_url,
    }
    try:
        response = requests.post(
            f"{API_URL}/apps/{pkgname}/fuzzers", headers=get_headers(), json=run_payload, timeout=30
        )
        response.raise_for_status()
        print(f"✅ Started fuzzer for {pkgname} ({binary})...")
        print(response.json())
    except Exception as e:
        print(f"❌ Failed to start fuzzer for {pkgname} ({binary}): {e}")
        return True

    return False


def upload_binary(pkgname: str, binary_name: str, binary_relpath: str, git_sha: str) -> bool:
    try:
        # Get presigned URL so we can use s3 uploading
        print(f"Getting presigned URL for {pkgname} ({binary_name})...")
        presigned_response = requests.post(
            f"{API_URL}/apps/{pkgname}/builds/{git_sha}/url", headers=get_headers(), timeout=30
        )

        presigned_response.raise_for_status()
        presigned_url = presigned_response.json()["data"]["url"]

        print(f"Uploading {pkgname} ({binary_name}) for {git_sha}...")
        # Upload file to presigned URL
        build_full_path = os.path.join(BUILD_BASE_PATH, binary_relpath)
        with open(build_full_path, "rb") as f:
            upload_response = requests.put(presigned_url, data=f, timeout=300)
            upload_response.raise_for_status()
    except Exception as e:
        print(f"❌ Failed to upload binary for {pkgname} ({binary_name}): {e}")
        return True
    return False


def get_headers():
    auth_header = (
        os.popen(f"{VAULT_PATH} read -field=token identity/oidc/token/security-fuzzing-platform").read().strip()
    )
    return {"Authorization": f"Bearer {auth_header}", "Content-Type": "application/json"}


if __name__ == "__main__":
    print("🚀 Starting fuzzing infrastructure setup...")
    try:
        build_and_upload_fuzz()
        print("✅ Fuzzing infrastructure setup completed successfully!")
    except Exception as e:
        print(f"❌ Failed to set up fuzzing infrastructure: {e}")
        sys.exit(1)
