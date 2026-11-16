---
name: check-delete-guard
description: Checks, without changing anything, whether the no_mass_delete hook from claude-code-safety-starter is installed in this project and really works, and explains the result in plain words. Use when the user asks "is my delete guard working?", "check the hook", "did I install it right?", or after a Claude Code update.
---

# check-delete-guard

You help someone who is not a programmer find out whether the `no_mass_delete` hook protects this
project. **You only look and report. You change nothing.**

## Hard rules

- Do not create, edit, copy, move or delete any file. Do not change `.claude/settings.json`.
- Do not "test" the hook by running a real delete command, even a harmless-looking one.
  `selftest.py` is the test: it only sends the hook descriptions of commands.
- Never suggest turning the hook off, removing it, or deleting files one at a time to get past it.
- Do not upload or send anything.
- If the user asks you to install or fix something, show the exact step from the README and let
  them do it, or tell them to ask you again in plain words after reading it.

## Steps

Do all steps in your first reply, then report. Don't stop to ask questions first.

1. **Python.** Run `python --version` on Windows, `python3 --version` on macOS/Linux. It must print
   `Python 3.x.x`.
2. **Files.** Check that `.claude/hooks/no_mass_delete.py` and `.claude/hooks/selftest.py` exist in
   the project folder (the folder Claude Code was started in).
3. **Settings.** Read `.claude/settings.json` (and `.claude/settings.local.json` if it exists).
   Look under `hooks` → `PreToolUse` for an entry whose `matcher` covers `Bash` and `PowerShell`
   and whose `args` (or `command`) points to `no_mass_delete.py`. Note if `disableAllHooks` is
   `true`: then no hook runs.
4. **Self-test.** If the two files exist, run `python .claude/hooks/selftest.py` (Windows) or
   `python3 .claude/hooks/selftest.py`. It deletes nothing. Read every `ok`, `FAIL` and `note` line.

## Report

Start with one sentence: **protected**, **not protected yet**, or **can't tell**.
"Protected" only when the self-test ends with `All checks passed`.

Then a short table:

| Checked | Result | What to do |
|---|---|---|
| Python 3 | ... | ... |
| Hook files in `.claude/hooks/` | ... | ... |
| Hook listed in settings | ... | ... |
| Self-test | ... (quote any FAIL line exactly) | ... |

Rules for the "What to do" column:
- Point to the matching step in the README's "Install (Windows, about 5 minutes)" section.
- For a FAIL line, say in one plain sentence what it means, then what the line itself says to fix.
- If everything passed, say: start a new Claude Code session, type `/hooks`, and check that the
  hook is listed. Remind them the hook is not a backup.

End with this sentence, without quotation marks: I didn't change anything.
