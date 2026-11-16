---
name: check-delete-guard
description: Checks, without changing anything, whether the no_mass_delete hook from claude-code-safety-starter is installed in this project and really works, and explains the result in plain words. Use when the user asks "is my delete guard working?", "check the hook", "did I install it right?", or after a Claude Code update.
---

# check-delete-guard

You help someone who is not a programmer find out whether the `no_mass_delete` hook protects this
project. **You only look and report. You change nothing.**

## Hard rules

- Do not create, edit, copy, move or delete any file. Do not change any settings file.
- Do not "test" the hook by running a real delete command, even a harmless-looking one.
  `selftest.py` is the test: it only sends the hook descriptions of commands.
- Never suggest turning the hook off, removing it, or deleting files one at a time to get past it.
- Do not upload or send anything.
- Do not fix anything during this check, even if the user asks. Tell them which step of the
  README to follow (see "Where to point them" below). If they want your help with a fix, that is a
  separate request after this check.

## Steps

Do all steps in your first reply, then report. Don't stop to ask questions first.

1. **Python.** Run `python --version` on Windows, `python3 --version` on macOS/Linux. If the
   settings (step 3) name a different program in `"command"` (for example `py`), run
   `<that program> --version` too. It must print `Python 3.x.x`.
2. **Files.** Check whether `.claude/hooks/no_mass_delete.py` and `.claude/hooks/selftest.py` exist
   in the project folder (the folder Claude Code was started in).
3. **Settings.** Read `.claude/settings.json` (and `.claude/settings.local.json` if it exists).
   Look under `hooks` → `PreToolUse` for an entry whose `matcher` covers `Bash` and `PowerShell`
   and whose `args` (or `command`) points to `no_mass_delete.py`. Also read, without changing it,
   `~/.claude/settings.json` if it exists. If `disableAllHooks` is `true` in any of these files,
   no hook runs.
4. **Self-test.** If `.claude/hooks/selftest.py` exists, run `python .claude/hooks/selftest.py`
   (Windows) or `python3 .claude/hooks/selftest.py`. It deletes nothing. Read every `ok`, `FAIL`
   and `note` line.

## Report

Start with one sentence: **protected**, **not protected yet**, or **can't tell**.
Say "protected" only when the self-test's last line starts with `All checks passed.` and no
settings file has `disableAllHooks: true`.

Then a short table:

| Checked | Result | What to do |
|---|---|---|
| Python 3 | ... | ... |
| Hook files in `.claude/hooks/` | ... | ... |
| Hook listed in settings | ... | ... |
| Self-test | ... (quote any FAIL line exactly) | ... |

### Where to point them

The README is `README.md` in the claude-code-safety-starter folder they downloaded, not in the project. Name the step; don't invent its
contents.

- Python missing or not Python 3 → README, "Before you start"
- Hook files missing → README, "Install", step 3
- Settings file missing, hook not listed, or the file is not valid JSON → README, "Install", step 4
- A FAIL line → say in one plain sentence what it means, then repeat what the line itself says to fix
- `disableAllHooks` is `true` → tell them hooks are switched off in that file, and that they decide
  whether to change it

If everything passed, say: start a new Claude Code session, type `/hooks`, and check that the
hook is listed. This is the final proof. Then add: the hook is not a backup, so keep a copy of the project somewhere else.

End with this sentence, without quotation marks: I didn't change anything.
