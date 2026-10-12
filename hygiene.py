#!/usr/bin/env python3
"""git-history-hygiene — audit a git history for hygiene problems.

Input: `git log --all --numstat --date=short --format=--C--|%H|%P|%ad|%s` text
(via --repo, --log-file, or stdin). Reports: large-file churn hotspots, merge
density, commit granularity, generic commit subjects, and a 0-100 hygiene score.
Pure stdlib.
"""
import argparse
import json
import re
import statistics
import subprocess
import sys

SEP = "--C--"
NUMSTAT_RE = re.compile(r"^(\d+|-)\t(\d+|-)\t(.+)$")
PATH_ESCAPE_RE = re.compile(r"\\(?:[0-9]{3}|\"|t|n)")

GENERIC_SUBJECTS = {"update", "fix", "wip", "changes", "misc", "tmp", "temp", "asdf", "test", "final", "final fix", "oops", "commit"}


def unquote_path(p):
    """Undo git's core.quotePath C-style escaping (\nnn octets, \" \\t \\n)."""
    if not isinstance(p, str):
        raise TypeError("path must be a string")
    if not (p.startswith('"') and p.endswith('"')):
        return p
    body = p[1:-1]
    out = []
    byte_buf = bytearray()
    i = 0
    while i < len(body):
        c = body[i]
        if c == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            if nxt == "t":
                out.append("\t")
                i += 2
                continue
            if nxt == "n":
                out.append("\n")
                i += 2
                continue
            if nxt == '"':
                out.append('"')
                i += 2
                continue
            if nxt == "\\":
                out.append("\\")
                i += 2
                continue
            m = re.match(r"\\([0-7]{3})", body[i:])
            if m:
                byte_buf.append(int(m.group(1), 8))
                i += 4
                continue
        if byte_buf:
            out.append(bytes(byte_buf).decode("utf-8", errors="replace"))
            byte_buf = bytearray()
        out.append(c)
        i += 1
    if byte_buf:
        out.append(bytes(byte_buf).decode("utf-8", errors="replace"))
    return "".join(out)


def parse_log(text):
    """Parse numstat log text -> list of commit dicts."""
    if text is None:
        raise ValueError("no log input")
    if not text.strip():
        raise ValueError("empty log input")
    commits = []
    cur = None
    for raw in text.splitlines():
        line = raw.rstrip("\r")
        if line.startswith(SEP + "|"):
            parts = line.split("|")
            if len(parts) < 5:
                raise ValueError("malformed commit header: %r" % line)
            _, h, parents, date, subject = parts[0], parts[1], parts[2], parts[3], "|".join(parts[4:])
            cur = {"hash": h, "parents": parents.split() if parents else [], "date": date, "subject": subject, "files": []}
            commits.append(cur)
        elif cur is not None and line.strip():
            m = NUMSTAT_RE.match(line.strip())
            if m:
                adds, dels, path = m.group(1), m.group(2), m.group(3)
                cur["files"].append({
                    "path": unquote_path(path),
                    "added": None if adds == "-" else int(adds),
                    "deleted": None if dels == "-" else int(dels),
                    "binary": adds == "-",
                })
    if not commits and text.strip():
        raise ValueError("no commit headers found in input")
    return commits


def analyze(commits, big_churn=2000, mega_files=50):
    if commits is None:
        raise TypeError("commits must be a list")
    if not commits:
        return {"commits": 0, "hygiene_score": 100, "findings": [], "metrics": {}}
    total = len(commits)
    merges = sum(1 for c in commits if len(c["parents"]) > 1)
    files_per_commit = [len(c["files"]) for c in commits]
    churn = {}
    binary_files = set()
    for c in commits:
        for f in c["files"]:
            if f["binary"]:
                binary_files.add(f["path"])
                continue
            churn[f["path"]] = churn.get(f["path"], 0) + f["added"] + f["deleted"]
    hotspots = sorted(churn.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    hotspots = [{"path": p, "churn": v} for p, v in hotspots if v >= big_churn]
    generic = [c["hash"][:8] for c in commits if c["subject"].strip().lower() in GENERIC_SUBJECTS]
    mega = [c["hash"][:8] for c in commits if len(c["files"]) > mega_files]

    findings = []
    if hotspots:
        findings.append({"id": "big-churn-file", "severity": "warn",
                         "detail": "%d file(s) with churn >= %d lines, e.g. %s" % (len(hotspots), big_churn, hotspots[0]["path"])})
    if merges / total > 0.3:
        findings.append({"id": "high-merge-density", "severity": "warn",
                         "detail": "%.0f%% of commits are merge commits (>30%% suggests noisy history)" % (100.0 * merges / total)})
    if files_per_commit and statistics.median(files_per_commit) > 20:
        findings.append({"id": "coarse-granularity", "severity": "warn",
                         "detail": "median files per commit is %d (>20 suggests bundled changes)" % statistics.median(files_per_commit)})
    if generic:
        findings.append({"id": "generic-subjects", "severity": "info",
                         "detail": "%d commit(s) with generic subjects like 'update'/'wip'" % len(generic)})
    if mega:
        findings.append({"id": "mega-commits", "severity": "info",
                         "detail": "%d commit(s) touch >%d files" % (len(mega), mega_files)})
    if binary_files:
        findings.append({"id": "binary-blobs", "severity": "info",
                         "detail": "%d binary file(s) in history" % len(binary_files)})

    score = 100
    score -= min(30, 6 * len(hotspots))
    score -= 20 if merges / total > 0.3 else 0
    score -= 15 if files_per_commit and statistics.median(files_per_commit) > 20 else 0
    score -= min(15, 3 * len(generic))
    score -= min(10, 2 * len(mega))
    score -= min(10, len(binary_files))
    score = max(0, score)
    return {
        "commits": total,
        "hygiene_score": score,
        "findings": findings,
        "metrics": {
            "merge_count": merges,
            "merge_density": round(merges / total, 4),
            "median_files_per_commit": statistics.median(files_per_commit),
            "p90_files_per_commit": sorted(files_per_commit)[min(len(files_per_commit) - 1, int(0.9 * (len(files_per_commit) - 1)))],
            "max_files_per_commit": max(files_per_commit),
            "generic_subject_count": len(generic),
            "mega_commit_count": len(mega),
            "binary_file_count": len(binary_files),
            "churn_hotspots": [{"path": h["path"], "churn": h["churn"]} for h in hotspots],
        },
    }


def get_log_text(repo):
    cmd = ["git", "-C", repo, "log", "--all", "--numstat", "--date=short", "--format=" + SEP + "|%H|%P|%ad|%s"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise ValueError("git log failed: %s" % proc.stderr.strip()[:200])
    return proc.stdout


def main(argv=None):
    ap = argparse.ArgumentParser(prog="git-history-hygiene", description="Audit git history hygiene: big files, merge density, granularity, generic subjects.")
    ap.add_argument("--repo", help="path to a git repository (runs git log via subprocess)")
    ap.add_argument("--log-file", help="pre-captured log text file (git log --numstat --format='--C--|%%H|%%P|%%ad|%%s')")
    ap.add_argument("--stdin", action="store_true", help="read log text from stdin")
    ap.add_argument("--big-churn", type=int, default=2000, help="churn threshold for file hotspots")
    ap.add_argument("--mega-files", type=int, default=50, help="files-per-commit threshold for mega commits")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    try:
        if args.repo:
            text = get_log_text(args.repo)
        elif args.log_file:
            with open(args.log_file, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        elif args.stdin:
            text = sys.stdin.read()
        else:
            ap.error("one of --repo / --log-file / --stdin is required")
            return 2
        report = analyze(parse_log(text), args.big_churn, args.mega_files)
    except (ValueError, OSError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("commits: %d   hygiene score: %d/100" % (report["commits"], report["hygiene_score"]))
        for f in report["findings"]:
            print("[%s] %s: %s" % (f["severity"], f["id"], f["detail"]))
        if not report["findings"]:
            print("no hygiene findings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
