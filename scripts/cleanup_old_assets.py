#!/usr/bin/env python3
"""
Automatically deletes GitHub releases, git tags, and workflow runs that are older than 7 days.
"""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

def run_command(cmd):
    """Run a system command and return the completed process."""
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result
    except FileNotFoundError:
        # Return a mock completed process if the executable itself is missing
        class MockCompletedProcess:
            def __init__(self, returncode, stdout, stderr):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr
        return MockCompletedProcess(127, "", f"Executable not found: {cmd[0]}")

def get_repo():
    return os.environ.get("GITHUB_REPOSITORY", "Droidspaces/Droidspaces-rootfs-builder")

def delete_tag_remote(tag):
    repo = get_repo()
    print(f"Attempting to delete remote tag {tag} via API...")
    cmd = ["gh", "api", "-X", "DELETE", f"repos/{repo}/git/refs/tags/{tag}"]
    res = run_command(cmd)
    if res.returncode == 0:
        print(f"Successfully deleted remote tag {tag}")
        return True
    else:
        print(f"Failed to delete remote tag {tag} (it might have already been deleted)")
        print(f"Stderr: {res.stderr.strip()}")
        return False

def main():
    print("Starting cleanup of old releases, tags, and workflow runs...")
    
    # Check if gh CLI is available
    if not shutil.which("gh"):
        print("Error: GitHub CLI 'gh' is not installed or not in PATH. Cleanup cannot proceed.")
        sys.exit(1)
        
    repo = get_repo()
    now = datetime.now(timezone.utc)
    
    # 1. Fetch tags from remote to make sure we have all of them
    print("Fetching tags from remote...")
    run_command(["git", "fetch", "--tags"])

    # 2. Cleanup old releases and tags
    print("Fetching all git tags with dates...")
    cmd = ["git", "for-each-ref", "--format=%(refname:short)|%(creatordate:iso-strict)|%(committerdate:iso-strict)", "refs/tags"]
    res = run_command(cmd)
    if res.returncode != 0:
        print("Failed to list git tags using git for-each-ref.")
        print(f"Stderr: {res.stderr}")
    else:
        tags_to_delete = []
        for line in res.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|")
            tag_name = parts[0]
            
            # Use creatordate if available, else committerdate
            date_str = parts[1] if parts[1] else parts[2]
            if not date_str:
                print(f"Skipping tag {tag_name} because no date was found.")
                continue
                
            try:
                # Handle iso-strict date formatting for Python compatibility
                if date_str.endswith('Z'):
                    date_str = date_str[:-1] + '+00:00'
                dt = datetime.fromisoformat(date_str).astimezone(timezone.utc)
                age = now - dt
                if age.days >= 7:
                    tags_to_delete.append((tag_name, date_str, age.days))
            except Exception as e:
                print(f"Error parsing date {date_str} for tag {tag_name}: {e}")
        
        # Fetch the latest release tag so we never delete it
        latest_tag = None
        latest_res = run_command(["gh", "release", "view", "--repo", repo, "--json", "tagName"])
        if latest_res.returncode == 0:
            try:
                latest_tag = json.loads(latest_res.stdout).get("tagName")
                print(f"Latest release tag (protected): {latest_tag}")
            except Exception:
                pass

        tags_to_delete = [(t, d, a) for t, d, a in tags_to_delete if t != latest_tag]
        print(f"Found {len(tags_to_delete)} tags older than 7 days (latest release protected).")
        deleted_releases = 0
        deleted_tags = 0

        for tag, date_str, days in tags_to_delete:
            print(f"Nuking tag/release {tag} (created {date_str}, age: {days} days)")
            
            # Try to delete release (this also cleans up the associated tag on GitHub)
            del_rel_cmd = ["gh", "release", "delete", tag, "--yes", "--cleanup-tag"]
            rel_res = run_command(del_rel_cmd)
            if rel_res.returncode == 0:
                deleted_releases += 1
                deleted_tags += 1
                print(f"Successfully deleted release and tag {tag}")
            else:
                # If release delete failed or didn't exist, try deleting tag directly
                print(f"Release delete failed/not found for tag {tag}. Trying to delete tag directly...")
                if delete_tag_remote(tag):
                    deleted_tags += 1
                    
        print(f"Cleanup of releases and tags completed. Deleted {deleted_releases} releases and {deleted_tags} tags.")

    # 3. Cleanup old workflow runs
    print("Fetching workflow runs...")
    cmd = ["gh", "run", "list", "--limit", "1000", "--json", "databaseId,createdAt"]
    res = run_command(cmd)
    if res.returncode != 0:
        print("Failed to list workflow runs.")
        print(f"Stderr: {res.stderr}")
    else:
        try:
            runs = json.loads(res.stdout)
            deleted_runs = 0
            for run in runs:
                run_id = str(run["databaseId"])
                created_at_str = run["createdAt"]
                
                # Parse date
                if created_at_str.endswith('Z'):
                    created_at_str = created_at_str[:-1] + '+00:00'
                dt = datetime.fromisoformat(created_at_str).astimezone(timezone.utc)
                age = now - dt
                if age.days >= 7:
                    print(f"Deleting workflow run {run_id} (created {created_at_str}, age: {age.days} days)")
                    del_cmd = ["gh", "run", "delete", run_id]
                    del_res = run_command(del_cmd)
                    if del_res.returncode == 0:
                        deleted_runs += 1
                        print(f"Successfully deleted workflow run {run_id}")
                    else:
                        print(f"Failed to delete workflow run {run_id}")
                        print(f"Stderr: {del_res.stderr.strip()}")
            print(f"Cleanup of workflow runs completed. Deleted {deleted_runs} runs.")
        except Exception as e:
            print(f"Error processing workflow runs: {e}")

if __name__ == "__main__":
    main()
