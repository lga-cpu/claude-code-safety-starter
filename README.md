# claude-code-safety-starter

**Stop Claude Code from deleting many files at once.** A free hook, a self-test and a one-page
checklist, for people who are not programmers.

Tested with Claude Code 2.1.280 on Windows 10 (Python 3.13), November 2026.

## Why a hook

Writing "never delete my files" in CLAUDE.md is not enough. Anthropic's documentation says
CLAUDE.md is context that Claude tries to follow, not something Claude Code enforces. To block an
action whatever Claude decides, it points to hooks.

A **hook** is a small script Claude Code runs before a tool (for example, before a shell command).
It can block the action.

This repository has one hook, `no_mass_delete`. It reads each shell command before it runs and
blocks the ones that can delete many files at once.

**It is not a backup.** Make a backup first (see "Before you start"). The hook is the second line.

## What's here

| | |
|---|---|
| `hooks/no_mass_delete.py` | The hook. Python 3, standard library only. |
| `hooks/selftest.py` | Checks that the hook really works on your computer. Deletes nothing. |
| `hooks/settings.example.windows.json` | Settings for Windows (uses `python`). |
| `hooks/settings.example.json` | Settings for macOS / Linux (uses `python3`). |
| `SKILL.md` | Optional skill `check-delete-guard`: Claude checks the install and explains the result. Edits no file. |
| `CHECKLIST.md` | One page: backup, install, check. |
| `LICENSE` | MIT. |

## What it blocks, asks about, and lets through

**Blocks** (in the Bash and PowerShell tools):
- recursive deletes: `rm -rf`, `Remove-Item -Recurse` (also `rm`, `ri`, `del`, `erase`, `rd`,
  `rmdir`), `rd /s`, `del /s`
- deletes with a wildcard: `rm *.txt`, `Remove-Item .\build\*`
- `del` / `erase` / `Remove-Item` on a folder
- `Remove-Item` with `-Include` / `-Exclude` / `-Filter`, or fed by a pipe; a delete inside a loop
- `git clean -f`, `find ... -delete`, `shutil.rmtree` in Python, `rimraf`
- wiping disks (`format C:`, `diskpart`, `cipher /w`, and others), `robocopy /mir` or `/purge`

**Asks you first** (a Yes/No question, not a block):
- one command that names two or more files: `rm a.txt b.txt`, `Remove-Item a.txt, b.txt`
- a delete whose list of files comes from another command: `rm $(cat list)`

**Lets through:** deleting one named file (`rm notes.txt`), text that only mentions a delete
(`echo "rm -rf"`), `git rm --cached`, `git clean -n`.

**Does not see** (a guard rail, not a guarantee):
- files deleted one at a time, each in its own command. If Claude offers to "delete them one at a
  time instead", that is a way around the hook. Look at the list and decide yourself.
- deletes inside a script file (`.ps1`, `.sh`, `.py`, `.js`)
- a delete started through another program (`timeout 30 rm -rf build`)
- a command name kept in a variable, `powershell -EncodedCommand`
- emptying or overwriting instead of deleting (`> file`, `git checkout -- .`, `git restore .`)
- moving files away (`mv`, `Move-Item`)
- commands run on another computer (`ssh host 'rm -rf ...'`)

The full list is at the top of `hooks/no_mass_delete.py`.

## Before you start

- **Python 3, as a real program.** On Windows, open PowerShell and type `python --version`. It
  must print `Python 3.x.x`. If it opens the Microsoft Store or prints nothing, install Python 3
  from python.org first. (macOS/Linux: `python3 --version`.)
- **A backup.** If your project folder were deleted right now, is there a copy somewhere else?
  If not, make one now. In PowerShell, in the project folder:
  ```
  tar -a -c -f ..\myproject-backup.zip .
  ```
  This puts a ZIP in the folder above your project, with everything in it, including hidden files
  and the `.git` folder. (`tar` comes with Windows 10 and 11. Don't use `Compress-Archive` for
  this: it leaves out hidden files.) Then copy the ZIP to a USB drive or a cloud folder yourself.
  (macOS/Linux: `zip -r ../myproject-backup.zip .`)
- Claude Code's `/rewind` is not a backup for this. Anthropic's documentation says files changed
  only by shell commands are not tracked, and a delete is usually a shell command.
- Don't keep the project inside the temp folder (`%TEMP%`).

## Install (Windows, about 5 minutes)

1. **Open PowerShell in your project folder.** In File Explorer, open the folder you start Claude
   Code in. Click the address bar, type `powershell`, and press Enter.
2. **Make the hooks folder:**
   ```
   mkdir .claude\hooks
   ```
   If it says the folder already exists, that is fine.
3. **Copy the two scripts.** In File Explorer, copy `hooks\no_mass_delete.py` and
   `hooks\selftest.py` from this repository into `<your project>\.claude\hooks\`.
4. **Add the settings.** First check whether you already have a settings file:
   ```
   Test-Path .claude\settings.json
   ```
   - `False`: copy `hooks\settings.example.windows.json` from this repository into `.claude\` and
     rename the copy to exactly `settings.json`. Turn on **View → File name extensions** in File
     Explorer first, or you may get `settings.json.json`, which Claude Code won't read.
   - `True`: don't replace it. Open it in Notepad. Under `"hooks"` → `"PreToolUse"` (a list), add
     the block from `settings.example.windows.json`, copied exactly, with its `"command"` **and**
     `"args"`. Mind the commas.
5. **Run the self-test:**
   ```
   python .claude\hooks\selftest.py
   ```
   A good run ends with
   `All checks passed. Now try it for real in a new Claude Code session (see README.md).`
   Any `FAIL` line means the hook is **not** protecting you yet. The line says what to fix.
6. **Start a new Claude Code session** and type `/hooks`. The hook should be listed.

**macOS / Linux** (not tested on a real machine): the same steps in Terminal, with
`mkdir -p .claude/hooks`, `cp` for copying, `settings.example.json` (it uses `python3`) and
`python3 .claude/hooks/selftest.py`.

### Why the settings look like this

Each entry names the program and its arguments separately:

```
{ "type": "command", "command": "python",
  "args": ["${CLAUDE_PROJECT_DIR}/.claude/hooks/no_mass_delete.py"] }
```

Anthropic's hooks documentation calls this the exec form. Claude Code starts the program directly,
with no shell. So it should not need Git Bash on Windows. That comes from the documentation; it was
tested only on a PC that has Git Bash. If `"command"` is not a working Python 3, Claude Code shows
only "hook error" and the hook blocks nothing. `selftest.py` checks this.

## Try it once

Make a dummy folder with one file in it, for example `test-delete\a.txt`. In the new session, ask
Claude: *"Run Remove-Item -Recurse -Force .\test-delete"*. You should see a message that starts
with `Blocked by the no_mass_delete safety hook`, and the folder should still be there.

Claude Code shows a block as `PreToolUse:Bash hook error: ...` (or `PreToolUse:PowerShell`).
Here "hook error" means the hook did its job. A block message **without** the hook's name comes
from Claude Code itself, not from this hook.

If Claude then suggests turning the hook off, don't do it straight away. Read why it stopped. If
you really want that delete, do it yourself in File Explorer (it uses the Recycle Bin), and leave
the hook on.

## Optional: let Claude check it for you

`SKILL.md` is a small skill called `check-delete-guard`. It checks Python, the two files, the
settings, and runs the self-test, then tells you in plain words whether you are protected. It only
looks: it edits no file and runs no real delete. (The self-test starts each Python hook listed in
your settings once. If you added other hooks of your own, they run once too.)

To use it:
1. In PowerShell, in your project folder:
   ```
   mkdir .claude\skills\check-delete-guard
   ```
2. Copy `SKILL.md` from this repository into that folder.
3. In a new Claude Code session, ask *"Is my delete guard working?"* or type
   `/check-delete-guard`. When Claude asks to run `python --version` and the self-test, choose Yes.

Tested only with Claude Haiku, on three dummy projects (hook installed, hook missing, wrong program
name in the settings): it gave the right answer each time and no file changed. Other models were
not tested.

## How it was tested

- Live runs in Claude Code 2.1.280 on Windows 10, with both the Bash tool and the PowerShell tool,
  with the settings in exec form.
- 225 unit tests for this hook, all passing. (The test file is not in this repository.)
- An independent tester tried to break it; the problems they found were fixed.

## Not tested

- A Windows PC without Git Bash
- macOS and Linux (the script is the same, but it was not run there)
- the Claude desktop app (Code tab) and the VS Code extension. Anthropic's documentation says hooks
  fire the same way there; this was not checked by hand.
- the Yes/No question in a normal session. In the test runs nobody could answer, so Claude Code
  refused the command, as the documentation says it does.

Claude Code changes quickly. After an update, run `selftest.py` again.

## The paid kit

This hook comes from the paid kit, *Claude Code Safety Kit for Non-Programmers*. It adds three more
hooks (changes outside the project folder, sending or publishing, risky git commands), two skills
(project setup, checking a "done" report), backup and install tools, and a 13-page guide.
US$19, one-time purchase, on Capafy
(https://capafy.ai/agent/claude-code-safety-kit-for-non-programmers/7726155401)
or Gumroad (https://lgafactory.gumroad.com/l/zvpgtz).

## License

MIT. See `LICENSE`. Not affiliated with or endorsed by Anthropic. "Claude" and "Claude Code" are
trademarks of Anthropic.
