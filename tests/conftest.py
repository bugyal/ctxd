"""Shared fixtures: generate the sample transcript and the file tree it refers to."""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

FIXTURE = os.path.join(HERE, "fixtures", "sample_session.jsonl")
F_APP = "/tmp/ctxd-fixture/proj/app.py"
F_UTIL = "/tmp/ctxd-fixture/proj/util.py"


@pytest.fixture(scope="session")
def tree(tmp_path_factory):
    """File tree the fixture transcript reads/edits.

    app.py on disk holds the OLD content (so it matches the recorded snapshot
    content-wise) — its staleness comes from the session's own later Write.
    util.py is read as lines 3..3 of a 5-line file and matches the disk.
    """
    d = tmp_path_factory.mktemp("ctxd-tree")
    app = d / "proj" / "app.py"
    app.parent.mkdir(parents=True)
    # NOTE: fixture reads F_APP (absolute /tmp path); tests copy the tree under
    # the same absolute paths because the transcript records absolute paths.
    os.makedirs("/tmp/ctxd-fixture/proj", exist_ok=True)
    with open(F_APP, "w") as fh:
        fh.write("value = 1\n")          # old content; session Write never ran
    with open(F_UTIL, "w") as fh:
        fh.write("a\nb\nhelper()\nd\ne\n")  # line 3 is helper()
    yield {"app": F_APP, "util": F_UTIL}
    for p in (F_APP, F_UTIL):
        try:
            os.unlink(p)
        except OSError:
            pass


@pytest.fixture(scope="session")
def session(tree):
    if not os.path.exists(FIXTURE):
        subprocess.run([sys.executable,
                        os.path.join(ROOT, "scripts", "make_fixture.py")],
                       check=True)
    return FIXTURE
