#!/usr/bin/env python3
"""Repeatedly re-merge origin/main into the session branch using a fixed, safe
conflict policy, push, and retry the PR merge.  Used because several parallel
sessions are landing on main simultaneously.

Conflict policy (never discards another session's work):
  * root *.html            -> take origin/main's file in full, then re-apply this
                              session's single additive nav anchor if missing
  * scripts/build_site.py  -> take origin/main's file, then ensure one NAV tuple
  * verification/links.json-> generated artifact: take origin/main's, regenerate
  * COORDINATION.md, README.md -> append-only logs: keep BOTH sides of each
                              conflict hunk (ours then theirs)
  * anything else          -> take origin/main's version
"""
import subprocess
import sys

MINE_HTML = '<a href="strategy-lab/index.html" class="">Strategy Lab</a>'
MINE_NAV = '    ("strategy-lab/index.html", "Strategy Lab"),\n'


def sh(*a, **kw):
    return subprocess.run(a, capture_output=True, text=True, **kw)


def ours_then_theirs(path):
    txt = open(path, encoding="utf-8").read()
    out, idx = [], 0
    start = txt.find("<<<<<<<")
    while start != -1:
        mid = txt.find("=======", start)
        end = txt.find(">>>>>>>", mid)
        if mid == -1 or end == -1:
            break
        out.append(txt[idx:start])
        out.append(txt[start + 7:mid].lstrip("\n"))
        out.append(txt[mid + 7:end].lstrip("\n"))
        idx = end + 7
        nl = txt.find("\n", idx)
        idx = nl + 1 if nl != -1 else len(txt)
        start = txt.find("<<<<<<<", idx)
    out.append(txt[idx:])
    open(path, "w", encoding="utf-8").write("\n".join(x for x in out if x != "") + "\n")


def resolve():
    files = sh("git", "diff", "--name-only", "--diff-filter=U").stdout.split()
    if not files:
        return []
    for f in files:
        base = f.split("/")[-1]
        if f.endswith(".html") and "/" not in f:
            t = sh("git", "show", "origin/main:" + f).stdout
            if "strategy-lab/index.html" not in t:
                t = t.replace("</nav>", MINE_HTML + "</nav>", 1)
            open(f, "w", encoding="utf-8").write(t)
        elif f == "scripts/build_site.py":
            t = sh("git", "show", "origin/main:" + f).stdout
            if "strategy-lab/index.html" not in t:
                t = t.replace("]\n\n\ndef data_version", MINE_NAV + "]\n\n\ndef data_version", 1)
            open(f, "w", encoding="utf-8").write(t)
        elif base in ("COORDINATION.md", "README.md"):
            ours_then_theirs(f)
        else:
            sh("git", "checkout", "--theirs", f)
    sh("git", "add", "-A")
    return files


def main():
    pr = sys.argv[1]
    for attempt in range(1, 9):
        sh("git", "fetch", "origin", "main")
        r = sh("git", "merge", "origin/main", "-m",
               "Merge origin/main into arena/b2d2460c-korea5 (integration pass %d)" % attempt)
        if r.returncode != 0:
            files = resolve()
            print("pass %d: resolved %d conflicted files: %s" % (attempt, len(files), ", ".join(files[:6])))
            c = sh("git", "commit", "-q", "-m",
                   "Merge origin/main into arena/b2d2460c-korea5 (pass %d); keep all sessions' work" % attempt)
            if c.returncode != 0:
                print("commit failed:", c.stderr[:400])
                return 1
        else:
            print("pass %d: already up to date" % attempt)
        cl = sh("python3", "scripts/check_links.py")
        print("  check_links:", cl.stdout.strip()[:120], "rc=%d" % cl.returncode)
        if cl.returncode != 0:
            print("  link check FAILED:", cl.stdout[-800:])
            return 1
        p = sh("git", "push")
        if p.returncode != 0:
            print("push failed:", p.stderr[:400])
            return 1
        m = sh("gh", "pr", "merge", pr, "--merge")
        if m.returncode == 0:
            print("PR %s MERGED on pass %d" % (pr, attempt))
            return 0
        print("  merge retry %d pending: %s" % (attempt, (m.stderr or m.stdout).strip()[:160]))
    print("gave up after 8 attempts")
    return 1


if __name__ == "__main__":
    sys.exit(main())
