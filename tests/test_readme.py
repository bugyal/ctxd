"""README drift: every documented command block must still produce its pasted output."""
import os
import re
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(ROOT, "README.md")
CTXD = os.path.join(os.path.dirname(sys.executable), "ctxd")


def readme_commands():
    text = open(README).read()
    return [line.strip()[2:] for line in text.splitlines()
            if line.strip().startswith("$ ctxd")]


@pytest.mark.parametrize("cmd", readme_commands(), ids=lambda c: c[:50])
def test_readme_command_still_output(cmd, tmp_path):
    # fixture tree the transcript refers to
    proj = tmp_path / "proj"
    proj.mkdir()
    os.makedirs("/tmp/ctxd-fixture/proj", exist_ok=True)
    with open("/tmp/ctxd-fixture/proj/app.py", "w") as fh:
        fh.write("value = 1\n")
    with open("/tmp/ctxd-fixture/proj/util.py", "w") as fh:
        fh.write("a\nb\nhelper()\nd\ne\n")
    session = os.path.join(ROOT, "tests", "fixtures", "sample_session.jsonl")
    real = cmd.replace("session.jsonl", session).replace("ctxd ", f'"{CTXD}" ', 1)
    rc = subprocess.run(real, shell=True, capture_output=True, text=True,
                        timeout=60)
    assert rc.returncode in (0, 1), f"command failed: {real}\n{rc.stderr}"
    out = rc.stdout

    # the pasted output lines after the $ line must appear (whitespace-normalised)
    text = open(README).read()
    pasted = _pasted_output_for(text, cmd)
    norm = lambda s: re.sub(r"\s+", " ", s).strip()
    for want in pasted:
        # session path is substituted, and a bare `...` elides rows
        if want.strip() in ("...", "…"):
            continue
        want_real = want.replace("session.jsonl", session)
        assert norm(want_real) in norm(out), \
            f"README output drifted.\ncommand: {real}\nexpected: {want!r}"


def _pasted_output_for(text, cmd):
    """Lines between the `$ <cmd>` line and the next blank/```/``$` boundary."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == f"$ {cmd}":
            out = []
            for l in lines[i + 1:]:
                if l.strip().startswith("$ ") or l.strip() == "```":
                    break
                out.append(l)
            return [l for l in out if l.strip()]
    return []


def test_pasted_output_lines_exist():
    """The README must actually contain parsed outputs, else the check is void."""
    total = sum(len(_pasted_output_for(open(README).read(), c))
                for c in readme_commands())
    assert total >= 10, "README checks found no pasted outputs; test is void"
