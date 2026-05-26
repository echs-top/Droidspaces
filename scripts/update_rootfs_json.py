#!/usr/bin/env python3
"""
Fetches the latest GitHub release metadata and updates rootfs.json
with direct download URLs, file sizes, checksums, architecture,
version and build date for each rootfs entry.
"""
import os
import sys
import json
import urllib.request
import urllib.error

API_URL = "https://api.github.com/repos/{repo}/releases/latest"

def fetch_latest_release(repo):
    """Fetch latest release metadata from the GitHub API."""
    url = API_URL.format(repo=repo)
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")

    # Use GITHUB_TOKEN if available (avoids rate limits in CI)
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Error fetching release from {url}: {e.code} {e.reason}")
        sys.exit(1)

def parse_asset_filename(name):
    """
    Parse a release asset filename into its components.
    Format: <PREFIX>-Droidspaces-rootfs-<ARCH>-<DATE>-<VERSION>.tar.xz
    Returns (prefix, arch, date, version) or None if the name doesn't match.
    """
    if "-Droidspaces-rootfs-" not in name:
        return None

    prefix, rest = name.split("-Droidspaces-rootfs-", 1)
    rest = rest.replace(".tar.xz", "")
    parts = rest.split("-")

    if len(parts) < 3:
        return None

    arch = parts[0]
    date_str = parts[1]
    version = "-".join(parts[2:])

    return prefix, arch, date_str, version

def find_matching_entry(entries, asset_prefix):
    """
    Match a release asset prefix (e.g. 'Alpine-Minimal') against the 'file'
    field in rootfs.json entries. The 'file' field may be a Dockerfile name
    like 'Alpine-Minimal.Dockerfile' or a bare prefix like 'NixOS-Minimal-Systemd-latest'.
    """
    for entry in entries:
        entry_file = entry.get("file", "")
        # Strip .Dockerfile extension for comparison
        entry_prefix = entry_file.replace(".Dockerfile", "")
        if entry_prefix == asset_prefix:
            return entry
    return None

def main():
    repo = os.environ.get("GITHUB_REPOSITORY", "Droidspaces/Droidspaces-rootfs-builder")

    # Locate rootfs.json
    json_path = sys.argv[1] if len(sys.argv) > 1 else "rootfs.json"
    if os.path.isdir(json_path):
        json_path = os.path.join(json_path, "rootfs.json")
    if not os.path.exists(json_path):
        print(f"Error: rootfs.json not found at {json_path}")
        sys.exit(1)

    with open(json_path, "r") as f:
        entries = json.load(f)

    # Fetch release data from GitHub API
    print(f"Fetching latest release from {repo}...")
    release = fetch_latest_release(repo)
    assets = release.get("assets", [])
    tag = release.get("tag_name", "")
    print(f"Release: {release.get('name', tag)} ({len(assets)} assets)")

    updated = 0
    for asset in assets:
        name = asset["name"]
        parsed = parse_asset_filename(name)
        if not parsed:
            print(f"  Skipping (not a rootfs tarball): {name}")
            continue

        prefix, arch, date_str, version = parsed
        entry = find_matching_entry(entries, prefix)

        if not entry:
            print(f"  No matching entry for: {prefix}")
            continue

        # Update entry with release metadata
        entry["architecture"] = arch
        entry["download_url"] = asset["browser_download_url"]
        entry["size_bytes"] = asset["size"]
        entry["version"] = version
        entry["build_date"] = date_str

        # Preserve existing author; set default if missing
        if "author" not in entry:
            entry["author"] = "Droidspaces developers"

        # GitHub API provides sha256 in the 'digest' field
        digest = asset.get("digest", "")
        if digest.startswith("sha256:"):
            entry["sha256"] = digest[len("sha256:"):]
        elif digest:
            entry["sha256"] = digest
        else:
            entry["sha256"] = ""

        updated += 1
        print(f"  Updated: {entry['name']} ({prefix})")

    # Write back
    with open(json_path, "w") as f:
        json.dump(entries, f, indent=2)
        f.write("\n")

    print(f"\nDone: {updated}/{len(assets)} assets matched and updated in {json_path}")

if __name__ == "__main__":
    main()
