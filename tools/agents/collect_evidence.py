#!/usr/bin/env python3
from __future__ import annotations

import datetime
import sys
from pathlib import Path

from common import ROOT, normalize_id, run_git

def collect_evidence(tid: str, *, root: Path = ROOT) -> Path:
    out=root/'agent'/'reports'/'qa'/f'{tid}-EVIDENCE.md'
    out.parent.mkdir(parents=True, exist_ok=True)
    rc,base,_=run_git('rev-parse','HEAD', root=root)
    _,status,_=run_git('status','--short', root=root)
    _,stat,_=run_git('diff','--stat', root=root)
    _,names,_=run_git('diff','--name-only', root=root)
    report=root/'agent'/'reports'/'implementation'/f'{tid}.md'
    text=f"""# Worker Evidence — {tid}\n\n- Generated: {datetime.datetime.now().isoformat(timespec="seconds")}\n- Base HEAD: {base if rc==0 else "Git unavailable"}\n\n## Git status\n```text\n{status or "clean"}\n```\n\n## Diff stat\n```text\n{stat or "none"}\n```\n\n## Changed tracked files\n```text\n{names or "none"}\n```\n\n## Implementation report\n- `{report.relative_to(root)}` — {'present' if report.exists() else 'MISSING'}\n\n## Note\nThis file records repository evidence; command-level test evidence belongs in the implementation report.\n"""
    out.write_text(text, encoding='utf-8')
    return out


def main():
    if len(sys.argv)!=2: raise SystemExit("Usage: collect-evidence TASK-0001")
    tid=normalize_id(sys.argv[1])
    out = collect_evidence(tid)
    print(out.relative_to(ROOT))


if __name__=='__main__':
    main()
