from __future__ import annotations
from pathlib import Path
import fnmatch
import hashlib
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REQUIRED_TASK_HEADINGS = [
    "## Goal", "## Requirement sources", "## Allowed paths", "## Worker profile", "## Acceptance criteria",
    "## Quality requirements", "## Test / verification plan", "## Security / privacy",
    "## Out of scope", "## Decision gate"
]
INFRA_PATH_PREFIXES = (
    'tools/agents/',
)
REQUIRED_REPORT_HEADINGS = [
    "## Status", "## Summary", "## Files changed", "## Acceptance criteria",
    "## Commands / verification executed", "## Security/privacy notes",
    "## Deviations from task/architecture", "## Known limitations / residual risk"
]

def normalize_id(raw: str) -> str:
    raw = raw.strip().upper()
    if raw.isdigit(): raw = f"TASK-{int(raw):04d}"
    if not re.fullmatch(r"TASK-\d{4,}", raw):
        raise ValueError("Task id must look like TASK-0001")
    return raw

def task_section(text: str, heading: str) -> str:
    match = re.search(rf"(?ms)^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)", text)
    return match.group(1).strip() if match else ""


def is_superseded_task(path: Path) -> bool:
    try:
        head = path.read_text(encoding="utf-8")[:2048]
    except OSError:
        return False
    return bool(re.search(r"(?im)^## Status\s*\n[^\n]*SUPERSEDED\b", head)) or "— SUPERSEDED" in head


def find_task_locations(
    task_id: str,
    folders=("ready", "active", "review", "blocked", "done", "backlog"),
    *,
    include_superseded: bool = False,
):
    locations = []
    for folder in folders:
        path = ROOT / "agent" / "tasks" / folder / f"{task_id}.md"
        if path.exists() and (include_superseded or not is_superseded_task(path)):
            locations.append((folder, path))
    return locations


def find_task(
    task_id: str,
    folders=("ready", "active", "review", "blocked", "done", "backlog"),
    *,
    include_superseded: bool = False,
):
    locations = find_task_locations(task_id, folders, include_superseded=include_superseded)
    if not locations:
        return None, None
    if len(locations) > 1:
        rendered = ", ".join(folder for folder, _ in locations)
        raise ValueError(f"{task_id} has multiple live task records: {rendered}")
    return locations[0]

def section_bullets(text: str, heading: str):
    section = task_section(text, heading)
    if not section:
        return []
    vals=[]
    for line in section.splitlines():
        line=line.strip()
        if line.startswith("-"):
            v=line[1:].strip().strip('`').strip()
            if v and not v.lower().startswith(("anything not", "product scope", "architecture/", "production deployment")):
                vals.append(v)
    return vals

def task_allowed_paths(text: str):
    return section_bullets(text, "Allowed paths")

def path_allowed(path: str, patterns):
    path=path.replace('\\','/').lstrip('./')
    for pat in patterns:
        pat=pat.replace('\\','/').lstrip('./')
        if fnmatch.fnmatchcase(path, pat): return True
        if pat.endswith('/**'):
            base=pat[:-3].rstrip('/')
            if path == base or path.startswith(base + '/'): return True
    return False

def sha_file(path: Path):
    if not path.exists(): return "<deleted>"
    if path.is_dir(): return "<dir>"
    h=hashlib.sha256()
    try:
        with path.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
        return h.hexdigest()
    except Exception:
        return "<unreadable>"

def git_dirty_state(root: Path = ROOT):
    cp=subprocess.run(["git","status","--porcelain=v1","-z","--untracked-files=all"],cwd=root,capture_output=True)
    if cp.returncode != 0: return None
    raw=cp.stdout.decode('utf-8','replace')
    parts=raw.split('\0')
    paths=[]
    i=0
    while i < len(parts):
        entry=parts[i]
        if not entry: i+=1; continue
        status=entry[:2]
        p=entry[3:] if len(entry)>=4 else ''
        if status[0] in {'R','C'}:
            # porcelain -z emits old then new; use both conservatively
            if p: paths.append(p)
            if i+1 < len(parts) and parts[i+1]: paths.append(parts[i+1]); i+=1
        elif p: paths.append(p)
        i+=1
    return {p: sha_file(root/p) for p in set(paths)}

def worker_changed_paths(before, after):
    if before is None or after is None: return None
    allp=set(before)|set(after)
    return sorted(p for p in allp if before.get(p,"<clean>") != after.get(p,"<clean>"))

def run_git(*args, root: Path = ROOT):
    cp=subprocess.run(["git",*args],cwd=root,text=True,capture_output=True)
    return cp.returncode, cp.stdout.strip(), cp.stderr.strip()
