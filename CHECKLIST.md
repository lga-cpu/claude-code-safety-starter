# Claude Code Safety — One-Page Checklist (free edition)

claude-code-safety-starter · tested with Claude Code 2.1.280 on Windows 10 · 2026-11-16

**1 · Can I get my files back?** (do this first)
- ☐ ZIP copy next to the project: `tar -a -c -f ..\myproject-backup.zip .` — then copy it to a USB drive or cloud yourself
- ☐ git snapshot, if you use git: check `git status` first (no password or key files), then `git add -A` and `git commit -m "Snapshot"`
- ☐ Not counting `/rewind` or a sync folder as the only backup
- ☐ Project is **not** inside the temp folder (`%TEMP%`)

**2 · Hard stops, not more rules** — ask of each rule: *"If broken once, can I undo it in minutes?"* No → a hard stop, enforced by a hook or a permission rule. Yes → a short **note** in CLAUDE.md.

| Hard stop | Enforced by |
|---|---|
| Don't delete many files | `no_mass_delete.py` (this repository) |
| Don't read `.env` / keys | permission `deny`: `Read(./.env)` + `.gitignore` |

Keep the hard stops few. Don't remove a rule from CLAUDE.md until its hook passed the self-test.

**3 · Installed and working?**
- ☐ `python --version` prints Python 3 (not the Microsoft Store)
- ☐ `no_mass_delete.py` and `selftest.py` in `.claude\hooks\`
- ☐ Settings **merged**, not replaced; the entry has `"command"` + `"args"`; not `settings.json.json`
- ☐ `python .claude\hooks\selftest.py` → "All checks passed" (macOS/Linux: `python3`); new session → `/hooks`
- ☐ One test block on a dummy folder, e.g. `Remove-Item -Recurse -Force .\test-delete`

**4 · When something is blocked or asked**
- ☐ Unfamiliar command, or a script file Claude wants to run? Ask what it does before Yes.
- ☐ Message names the hook → the hook stopped it; read why. No hook name → Claude Code itself stopped it.
- ☐ Claude says "turn the hook off" or "delete them one at a time"? Don't, yet. Decide yourself; Explorer uses the Recycle Bin.

**5 · Before anything leaves the computer**
- ☐ Submit, send, publish, pay: a person presses the last button

**6 · After a Claude Code update:** selftest again → `/hooks` → one dummy test. A guard rail, not a guarantee — the backup comes first.
