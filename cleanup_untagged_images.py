#!/usr/bin/env python3
"""Delete untagged GHCR container image versions older than 6 months."""

import os
import sys
from datetime import datetime, timedelta, timezone

import urllib.request
import urllib.error
import json


def github_api_request(url, token, method="GET"):
    req = urllib.request.Request(
        url,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            if resp.status == 204:
                return None
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTP error {e.code} for {method} {url}: {e.reason}", file=sys.stderr)
        raise


def get_all_versions(token, owner, package_name):
    versions = []
    page = 1
    while True:
        url = (
            f"https://api.github.com/users/{owner}/packages/container"
            f"/{package_name}/versions?per_page=100&page={page}"
        )
        page_data = github_api_request(url, token)
        if not page_data:
            break
        versions.extend(page_data)
        if len(page_data) < 100:
            break
        page += 1
    return versions


def delete_version(token, owner, package_name, version_id):
    url = (
        f"https://api.github.com/users/{owner}/packages/container"
        f"/{package_name}/versions/{version_id}"
    )
    github_api_request(url, token, method="DELETE")


def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    repository = os.environ.get("GITHUB_REPOSITORY")
    if not repository:
        print(
            "Error: GITHUB_REPOSITORY environment variable is not set.", file=sys.stderr
        )
        sys.exit(1)

    if "/" not in repository:
        print(
            "Error: GITHUB_REPOSITORY must be in the format 'owner/repo'.",
            file=sys.stderr,
        )
        sys.exit(1)
    owner, repo_name = repository.split("/", 1)
    package_name = repo_name

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=2 * 365)

    print(f"Fetching versions for {owner}/{package_name}...")
    versions = get_all_versions(token, owner, package_name)
    print(f"Found {len(versions)} total version(s).")

    deleted = 0
    for version in versions:
        tags = version.get("metadata", {}).get("container", {}).get("tags", [])
        if tags:
            continue  # skip tagged versions

        created_at_str = version.get("created_at", "")
        created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))

        if created_at < cutoff:
            version_id = version["id"]
            print(
                f"Deleting untagged version {version_id} "
                f"(created {created_at.date()})..."
            )
            delete_version(token, owner, package_name, version_id)
            deleted += 1

    print(f"Done. Deleted {deleted} untagged image version(s) older than 2 years.")


if __name__ == "__main__":
    main()
