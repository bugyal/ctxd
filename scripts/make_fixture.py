#!/usr/bin/env python3
"""Generate tests/fixtures/sample_session.jsonl.

Shape mirrors real Claude Code transcripts on this machine (verified against
~/.claude/projects records): assistant records with usage, user-side
toolUseResult read snapshots, tool_use Write/Edit records. The fixture is
synthetic but structurally faithful; personal paths are not involved because
the fixture uses a scratch tree that the tests create.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # repo root
OUT = os.path.join(ROOT, "tests", "fixtures", "sample_session.jsonl")

F = "/tmp/ctxd-fixture/proj/app.py"

records = [
    # turn 0: read the file (usage small)
    {"type": "assistant", "message": {"role": "assistant", "model": "test-model",
     "content": [{"type": "tool_use", "id": "call_1", "name": "Read",
                  "input": {"file_path": F}}],
     "usage": {"input_tokens": 1200, "cache_read_input_tokens": 800,
               "cache_creation_input_tokens": 0, "output_tokens": 50}},
     "timestamp": "2026-10-06T08:00:00.000Z", "uuid": "u0"},
    {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "call_1",
         "content": [{"type": "text", "text": "1\tvalue = 1\n"}]}]},
     "toolUseResult": {"type": "text", "file": {"filePath": F,
                     "content": "value = 1\n", "numLines": 1, "startLine": 1,
                     "totalLines": 1}},
     "timestamp": "2026-10-06T08:00:01.000Z", "uuid": "u1",
     "sourceToolAssistantUUID": "u0"},
    # turn 1: model CLAIMS context is nearly full (a lie — usage says 2050)
    {"type": "assistant", "message": {"role": "assistant", "model": "test-model",
     "content": [{"type": "text", "text":
                  "I am almost out of context window, I cannot continue."}],
     "usage": {"input_tokens": 1500, "cache_read_input_tokens": 500,
               "cache_creation_input_tokens": 50, "output_tokens": 30}},
     "timestamp": "2026-10-06T08:00:02.000Z", "uuid": "u2"},
    # turn 2: edit the file (stales the view above)
    {"type": "assistant", "message": {"role": "assistant", "model": "test-model",
     "content": [{"type": "tool_use", "id": "call_2", "name": "Write",
                  "input": {"file_path": F, "content": "value = 2\n"}}],
     "usage": {"input_tokens": 2000, "cache_read_input_tokens": 3000,
               "cache_creation_input_tokens": 400, "output_tokens": 60}},
     "timestamp": "2026-10-06T08:00:03.000Z", "uuid": "u3"},
    # turn 3: read a second file that stays fresh
    {"type": "assistant", "message": {"role": "assistant", "model": "test-model",
     "content": [{"type": "tool_use", "id": "call_3", "name": "Read",
                  "input": {"file_path": "/tmp/ctxd-fixture/proj/util.py"}}],
     "usage": {"input_tokens": 2500, "cache_read_input_tokens": 3000,
               "cache_creation_input_tokens": 100, "output_tokens": 40}},
     "timestamp": "2026-10-06T08:00:04.000Z", "uuid": "u4"},
    {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "call_3",
         "content": "3\thelper()\n"}]},
     "toolUseResult": {"type": "text", "file": {
         "filePath": "/tmp/ctxd-fixture/proj/util.py",
         "content": "helper()\n", "numLines": 1, "startLine": 3,
         "totalLines": 5}},
     "timestamp": "2026-10-06T08:00:05.000Z", "uuid": "u5"},
    # a record type we do not know — skipped
    {"type": "summary", "summary": "irrelevant"},
]

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as fh:
    for r in records:
        fh.write(r if isinstance(r, str) else json.dumps(r))
        fh.write("\n")
print(f"wrote {OUT}")
