"""ctxd — agent stale-context detection.

Ground truth about an agent session's context, from the harness's own records:

1. **Context ledger** — real token counts taken from provider usage records in a
   Claude Code session transcript. Never from anything the model said about its
   own context.
2. **Stale file-view detection** — every Read snapshot recorded in the transcript
   is hashed; a snapshot is stale when the underlying file has changed since
   (checked against the filesystem) or when the same session edited the file
   after reading it (checkable from the transcript alone).
3. **Pre-flight gating** — one command a harness can run before the next tool
   call: exit 0 to proceed, exit 1 when headroom is low or stale views exist.

Design rules:

- **Measured vs estimated is never blended.** Token counts come only from
  `usage` records. Cost estimates for a file view are labelled estimated.
- **Verdicts come from records, not from the model's account.** ctxd never
  parses prose to decide how much context is left.
- `main` returns exit codes and never leaks a traceback: usage problems raise
  UsageError and render as `ctxd: <message>` on stderr with exit 2.
"""

__version__ = "0.1.0"
