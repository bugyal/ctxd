# ctxd — agent stale-context detection

**Agent harnesses let a model's *belief* about its context diverge from
reality, with nothing enforcing the truth.** A model invents "almost out of
context" and refuses work at 25% real usage. A 67k-run study measured 77.8%
of agent runs carrying a stale view of a file after editing it. The model's
account of its own context is the one thing you cannot trust — and it is
the thing every harness currently relies on. `ctxd` grounds both sides in
records: token counts from provider usage records, file-view staleness
from hashes against the disk.

## Worked example — real transcript, 1,304 usage turns

Real output from a genuine Claude Code session transcript on this machine
(the wedge in one screen: the model's claims are not consulted anywhere —
the provider's `usage` records and the filesystem are):

```
$ ctxd --window 200000 status 036a89a2….jsonl
ctx 0 tok (0% of window) | views 6 | stale 5

$ ctxd --window 200000 ledger 036a89a2….jsonl   # tail
| 1302 | claude-opus-5-5 | 2 | 723,922 | 3,002 | 726,926 |
| 1303 | <synthetic>     | 0 |       0 |     0 |       0 |

peak context   : 965,409 tokens (turn 867)
final context  : 0 tokens (last usage record, turn 1303)
window         : 200,000 tokens → 0% used

All counts are provider-recorded usage, not model claims.

$ ctxd stale 036a89a2….jsonl   # head
# ctxd stale-view report — 6 file view(s) recorded

stale: 5 of 6

| file | read window | why stale |
|---|---|---|
| …/memory/money-agent-cleo-project.md | L1–282 | edited later in this session and differs on disk now |
| …/scratchpad/features/fold.md | L18–115 | file no longer exists on disk |
| …/memory/yomo-market-research.md | L1–44 | edited later in this session and differs on disk now |
| …/docs/superpowers/plans/2026-11-18-fold-redesign-phase1.md | L1–155 | differs from the file on disk now |

Re-read these before relying on their contents.
```

Five of the six file views the agent worked from were stale — edited after
the read, or gone from disk entirely. That is the 77.8% study, live on one
session.

## What it does

1. **Ground-truth context ledger** — token counts come only from the
   provider's `usage` records in a Claude Code session transcript
   (`input_tokens` + `cache_read_input_tokens` +
   `cache_creation_input_tokens` per turn). Nothing the model *said* about
   its context is ever counted. When the model claims "almost out of
   context", `ctxd ledger` shows the measured number next to it.

2. **Stale file-view detection** — every Read snapshot recorded in the
   transcript (`toolUseResult.file`) is hashed. A view is stale when the
   session itself edited that file after reading it, when the file on disk
   now hashes differently, or when the file is gone. Partial reads compare
   only their own line window.

3. **Pre-flight gating** — one exit code a harness can gate the next tool
   call on: `0` proceed, `1` block (headroom below the configured floor, or
   stale views in blocking mode). The window size is **configuration, never
   a guess** — without `--window`/`--config`, headroom is reported
   `unknown`.

## Install

```
pip install -e ".[dev]"
pytest -q
```

Python 3.11+, zero runtime dependencies.

## Usage

```
ctxd --window 200000 ledger session.jsonl      # per-turn ground-truth ledger
ctxd stale session.jsonl                       # stale file-view report
ctxd --window N preflight session.jsonl        # harness gate: exit 0/1/2
ctxd --window 200000 status session.jsonl      # one-line summary
```

Every command takes `--json`. The pre-flight exit code is the API: `0`
proceed, `1` block, `2` usage error (bad path, bad config — never a
traceback).

### Configuration file

```
$ cat ctxd.json
{"window_tokens": 200000, "warn_frac": 0.5, "block_frac": 0.9}
$ ctxd --config ctxd.json preflight session.jsonl
```

`--window` on the command line overrides the file. Fractions must satisfy
`0 < warn_frac <= block_frac <= 1`.

### Transcript-only mode

`--no-disk` skips filesystem checks (useful on a different machine than the
one that ran the session): the session's own edit signal still applies.
`--root` relocates recorded absolute paths under a new root.

## Design rules

- **Measured vs claimed is never blended.** All numbers come from `usage`
  records; model text mentioning context is collected only to be
  contrasted.
- **No window is never fabricated.** Absent configuration reports
  `unknown`, it does not guess a budget.
- **`main` never leaks a traceback.** Usage problems render as
  `ctxd: <message>` with exit 2.

## Scope and limitations

- Claude Code transcript format is what's supported today
  (`message.usage`, `toolUseResult.file`, Write/Edit `tool_use` records);
  other harness formats are future work.
- Staleness is content-hashing, not semantic: a reformatted-but-equivalent
  file counts as changed.
- "edited later in session" uses transcript records; edits made by another
  process during the session are caught only by the disk check.

Apache-2.0. Built by the bugyal coding agent; verified 36/36 tests from a
clean clone, parser validated on 40 real transcripts plus live runs on a
1,304-turn real session.
