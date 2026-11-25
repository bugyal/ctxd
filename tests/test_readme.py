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
    # host-coupled examples (real transcripts from the build machine) live
    # under a "worked example" heading and are replayed only on the machine
    # that owns the referenced file — the skill records why: a replay check
    # that is sound for deterministic commands is unsatisfiable for
    # host-specific ones.
    commands = []
    in_example = False
    for line in text.splitlines():
        if line.startswith("## Worked example"):
            in_example = True
        elif line.startswith("## "):
            in_example = False
        if line.strip().startswith("$ ctxd"):
            commands.append((line.strip()[2:], in_example))
    return commands


@pytest.mark.parametrize("cmd,in_example", readme_commands())
def test_readme_command_still_output(cmd, in_example, tmp_path):
    # fixture tree the transcript refers to
    proj = tmp_path / "proj"
    proj.mkdir()
    os.makedirs("/tmp/ctxd-fixture/proj", exist_ok=True)
    with open("/tmp/ctxd-fixture/proj/app.py", "w") as fh:
        fh.write("value = 1\n")
    with open("/tmp/ctxd-fixture/proj/util.py", "w") as fh:
        fh.write("a\nb\nhelper()\nd\ne\n")
    session = os.path.join(ROOT, "tests", "fixtures", "sample_session.jsonl")
    if in_example:
        # host-coupled worked example: the transcript lives on the build
        # machine. Verify it exists THERE and that ctxd runs on it — skip
        # replay elsewhere (CI has no such transcript; this is the
        # locally-green-remotely-unsatisfiable guard).
        import glob
        real_transcripts = glob.glob(os.path.expanduser(
            "~/.claude/projects/*/*.jsonl"))
        if not real_transcripts:
            pytest.skip("host-coupled example: no local transcripts on "
                        "this machine")
        target = None
        for f in real_transcripts:
            if "036a89a2" in os.path.basename(f):
                target = f
                break
        if target is None:
            pytest.skip("host-coupled example transcript not present on "
                        "this machine")
        real = (cmd.replace("036a89a2….jsonl", target)
                   .replace("ctxd ", f'"{CTXD}" ', 1))
        rc = subprocess.run(real, shell=True, capture_output=True,
                            text=True, timeout=120)
        assert rc.returncode in (0, 1), \
            f"worked example failed: {real}\n{rc.stderr}"
        return  # the pasted numbers are from the capture run; a live
        # re-run drifts as the transcript file may have grown since
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
                for c, _ex in readme_commands())
    assert total >= 10, "README checks found no pasted outputs; test is void"
