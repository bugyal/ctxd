# ctxd — agent stale-context detection

Agent harnesses let a model's *belief* about its context diverge from reality,
with nothing enforcing the truth: a model invents "almost out of context" and
refuses work at 25% real usage; a 67k-run study found 77.8% of agent runs
carrying a stale view of a file after editing it. `ctxd` grounds both in
records instead of claims.

```
$ ctxd --window 200000 status session.jsonl
ctx 5,600 tok (3% of window) | views 2 | stale 1
```

## What it does

1. **Ground-truth context ledger** — token counts come only from the
   provider's `usage` records in a Claude Code session transcript
   (`input_tokens` + `cache_read_input_tokens` +
   `cache_creation_input_tokens` per turn). Nothing the model *said* about its
   context is ever counted. When the model claims "almost out of context",
   `ctxd ledger` shows the measured number next to it.

2. **Stale file-view detection** — every Read snapshot recorded in the
   transcript (`toolUseResult.file`) is hashed. A view is stale when the
   session itself edited that file after reading it, when the file on disk now
   hashes differently, or when the file is gone. Partial reads compare only
   their own line window.

3. **Pre-flight gating** — one exit code a harness can gate the next tool call
   on: `0` proceed, `1` block (headroom below the configured floor, or stale
   views in blocking mode). The window size is **configuration, never a
   guess** — without `--window`/`--config`, headroom is reported `unknown`.

## Install

```
pip install -e ".[dev]"
```

## Usage

```
$ ctxd --window 200000 ledger session.jsonl
# ctxd ledger — session.jsonl

| turn | model | input | cache_read | cache_new | context total |
|---|---|---|---|---|---|
| 0 | test-model | 1,200 | 800 | 0 | 2,000 |
...
peak context   : 5,600 tokens (turn 3)
final context  : 5,600 tokens (last usage record, turn 3)
window         : 200,000 tokens → 3% used

All counts are provider-recorded usage, not model claims.

$ ctxd stale session.jsonl
# ctxd stale-view report — 2 file view(s) recorded

stale: 1 of 2

| file | read window | why stale |
|---|---|---|
| `/tmp/ctxd-fixture/proj/app.py` | L1–1 | edited later in this session |

Re-read these before relying on their contents.

$ ctxd --window 100000 preflight session.jsonl
ctxd preflight: WARN
  context: 5,600 / 100,000 tokens (6% used), 94,400 free
  stale views: 1 — re-read before relying on them
  - 1 file view(s) are stale; re-read before relying on them

$ ctxd --window 100000 preflight session.jsonl --stale-blocks
ctxd preflight: BLOCK
  ...
```

Every command takes `--json` for machine-readable output. The pre-flight exit
code is the API: `0` proceed, `1` block, `2` usage error (bad path, bad
config — never a traceback).

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
  records; model text mentioning context is collected only to be contrasted.
- **No window is never fabricated.** Absent configuration reports `unknown`,
  it does not guess a budget.
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
