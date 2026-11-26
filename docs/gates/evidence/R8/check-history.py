"""Inventory tracked and reachable release material without printing matched secrets."""
import json
from pathlib import PurePosixPath
import re
import subprocess


def git(*args):
    return subprocess.check_output(("git", *args))


host_path = re.compile(rb"(?i)/Users/[^/\s\"']+/|/home/(?!runner/)[^/\s\"']+/|[A-Z]:[\\/]+Users[\\/]")
credential = re.compile(
    rb"-----BEGIN (?:OPENSSH |RSA |EC |DSA |ENCRYPTED )?PRIVATE KEY-----"
    rb"|\b(?:gh[pousr]_[a-zA-Z0-9]{36,}|github_pat_[a-zA-Z0-9_]{40,}|(?:AKIA|ASIA)[A-Z0-9]{16})\b"
)
cache_names = {".venv", "__pycache__", "CMakeFiles", ".pytest_cache"}
commit = subprocess.Popen(("git", "cat-file", "--batch"), stdin=subprocess.PIPE, stdout=subprocess.PIPE)


def scan(objects):
    result = {"blobs_checked": 0, "host_path_hits": [], "credential_hits": [],
              "intermediate_path_hits": [], "blobs_over_10_mib": [], "largest_blob": 0}
    for sha, name in objects.items():
        commit.stdin.write(sha + b"\n")
        commit.stdin.flush()
        _, kind, declared = commit.stdout.readline().split()
        size = int(declared)
        data = commit.stdout.read(size)
        assert len(data) == size and commit.stdout.read(1) == b"\n"
        if kind != b"blob":
            continue
        result["blobs_checked"] += 1
        result["largest_blob"] = max(result["largest_blob"], size)
        key = {"path": name, "oid": sha.decode(), "bytes": size}
        if host_path.search(data):
            result["host_path_hits"].append(key)
        if credential.search(data):
            result["credential_hits"].append(key)
        if cache_names.intersection(PurePosixPath(name).parts) or PurePosixPath(name).suffix in {".pyc", ".o", ".obj", ".so", ".pyd", ".whl"}:
            result["intermediate_path_hits"].append(key)
        if size > 10 * 1024 * 1024:
            result["blobs_over_10_mib"].append(key)
    return result


def tree(sha):
    entries = (row.split(b"\t", 1) for row in git("ls-tree", "-rz", sha).split(b"\0") if row)
    return {header.split()[-1]: path.decode(errors="replace") for header, path in entries
            if header.split()[1] == b"blob"}


def reachable(*refs):
    rows = (line.split(b" ", 1) for line in git("rev-list", "--objects", *refs).splitlines())
    return {sha: name.decode(errors="replace") for sha, name in (row for row in rows if len(row) == 2)}


remote_heads = git("for-each-ref", "--format=%(refname)", "refs/remotes/origin").decode().splitlines()
remote_heads = [ref for ref in remote_heads if not ref.endswith("/HEAD")]
candidate = reachable("HEAD")
published = reachable(*remote_heads)
paths = tree("HEAD")
print(json.dumps({
    "scope": "Known working-tree and Git-object patterns; archive formats are inventoried separately",
    "published_ref_count": len(remote_heads),
    "published_history": scan(published),
    "candidate_history_delta": scan({sha: name for sha, name in candidate.items() if sha not in published}),
    "candidate_tree": scan(paths),
}, indent=2))
commit.stdin.close()
assert commit.wait() == 0
