#!/usr/bin/env python3
# Part of claude-code-safety-starter, the free edition of the Claude Code Safety Kit for Non-Programmers. (c) 2026 LGA. MIT License; see LICENSE.
"""Check the no_mass_delete hook in THIS project before you rely on it.

Run from your project folder:
    python3 .claude/hooks/selftest.py        (macOS / Linux)
    python  .claude/hooks/selftest.py        (Windows)

It checks:
1. that .claude/settings.json exists and is valid, and that no_mass_delete.py in .claude/hooks/
   is registered in it (or in .claude/settings.local.json);
2. that the registered hook really starts the way Claude Code starts it, with the program
   named in the settings (python3 / python / py) - if a hook cannot start, Claude Code shows
   only "hook error" and the hook blocks nothing;
3. that the hook stops commands it should stop and lets a harmless command through.
Nothing is deleted, sent or changed: the hook only reads a description of a command.
Exit code 0 only when every check passed. Standard library only.
"""
import glob
import json
import os
import re
import shlex
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(os.path.dirname(HERE))
KIT_HOOKS = ["no_mass_delete.py"]
results = []


def report(ok, text):
    results.append(ok)
    print(("  ok    " if ok else "  FAIL  ") + text)


def note(text):
    print("  note  " + text)


def run(script, payload):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": PROJECT}
    p = subprocess.run([sys.executable, os.path.join(HERE, script)], input=json.dumps(payload),
                       capture_output=True, text=True, env=env)
    try:
        return json.loads(p.stdout) if p.stdout.strip() else {}
    except ValueError:
        return {"_error": p.stdout + p.stderr}


def decision(out):
    return (out.get("hookSpecificOutput") or {}).get("permissionDecision")


def shell(cmd, tool="Bash"):
    return {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {"command": cmd}, "cwd": PROJECT}


def find_git_bash():
    """Where Claude Code would find Git Bash on Windows, or None."""
    if os.environ.get("CCSK_SELFTEST_NO_GIT_BASH"):  # for testing: behave as if Git Bash were not installed
        return None
    env_path = os.environ.get("CLAUDE_CODE_GIT_BASH_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path
    git = shutil.which("git")
    candidates = []
    if git:
        root = os.path.dirname(os.path.dirname(git))  # ...\Git\cmd\git.exe -> ...\Git
        candidates.append(os.path.join(root, "bin", "bash.exe"))
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"),
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")):
        if base:
            candidates.append(os.path.join(base, "Git", "bin", "bash.exe"))
    return next((c for c in candidates if os.path.isfile(c)), None)


# ---------------------------------------------------------------- 1. settings
print("1. .claude/settings.json")
claude_dir = os.path.join(PROJECT, ".claude")
entries = []  # dicts: file, event, matcher, command, args (list or None)
found_settings = False
disable_all = {}  # file -> value of disableAllHooks
for fname in ("settings.json", "settings.local.json"):
    path = os.path.join(claude_dir, fname)
    if not os.path.exists(path):
        continue
    found_settings = True
    try:
        with open(path, encoding="utf-8-sig") as f:
            settings = json.load(f)
    except ValueError as e:
        report(False, f"{fname} is not valid JSON: {e}. Claude Code will not load any hook from it.")
        continue
    except OSError as e:
        report(False, f"cannot read {fname}: {e}")
        continue
    report(True, f"{fname} is valid JSON")
    if not isinstance(settings, dict):
        report(False, f"{fname} must be a JSON object {{ ... }}")
        continue
    if "disableAllHooks" in settings:
        disable_all[fname] = settings.get("disableAllHooks")
    for event, groups in (settings.get("hooks") or {}).items():
        for group in groups or []:
            for h in (group or {}).get("hooks") or []:
                if h.get("type") == "command":
                    entries.append({"file": fname, "event": event, "matcher": group.get("matcher", "") or "",
                                    "command": h.get("command", "") or "", "args": h.get("args")})

if not found_settings:
    near_misses = [os.path.basename(p) for p in glob.glob(os.path.join(claude_dir, "settings*"))]
    hint = ""
    if near_misses:
        hint = (f" Found {', '.join(near_misses)} instead. Windows hides file extensions, so a file you renamed "
                "to 'settings.json' may really be 'settings.json.json'. Rename it so the name is exactly settings.json.")
    report(False, "No .claude/settings.json. Without it Claude Code runs none of the hooks. Copy "
                  "settings.example.windows.json (Windows) or settings.example.json (Mac/Linux) to "
                  ".claude/settings.json." + hint)


def script_of(entry):
    """The .py file a hook entry runs, with the project folder filled in, or None."""
    parts = list(entry["args"]) if isinstance(entry["args"], list) else [entry["command"]]
    for part in parts:
        m = re.search(r"([^\s\"']*\.py)\b", part)
        if m:
            s = m.group(1)
            for ph in ("${CLAUDE_PROJECT_DIR}", "$CLAUDE_PROJECT_DIR", "$env:CLAUDE_PROJECT_DIR", "%CLAUDE_PROJECT_DIR%"):
                s = s.replace(ph, PROJECT)
            return s if os.path.isabs(s) else os.path.join(PROJECT, s)
    return None


pre = [e for e in entries if e["event"] == "PreToolUse"]
if found_settings and not pre:
    report(False, "No PreToolUse hooks are registered, so no_mass_delete does not run. Add the \"hooks\" block "
                  "from settings.example.windows.json (Windows) or settings.example.json (Mac/Linux).")

present = set(os.listdir(HERE))
registered = {}
for e in pre:
    s = script_of(e)
    if s:
        registered.setdefault(os.path.basename(s), []).append(e)
for name in KIT_HOOKS:
    if name in present and found_settings and pre:
        report(name in registered, f"{name} is registered in the settings" if name in registered else
               f"{name} is in .claude/hooks/ but NOT registered in the settings, so it does nothing. "
               "Add its entry from settings.example*.json.")

# settings.local.json wins over settings.json (official docs: settings precedence)
effective_disable = disable_all.get("settings.local.json", disable_all.get("settings.json"))
if effective_disable is True:
    where = "settings.local.json" if disable_all.get("settings.local.json") is True else "settings.json"
    report(False, f'"disableAllHooks": true in {where} turns off every hook. Remove that line (or set it to false).')


def matcher_matches(matcher, tool):
    """How Claude Code reads a matcher (official docs, 'Matcher patterns'): '*', '' or none match everything;
    only letters, digits, _ - space , | -> exact names (case matters); anything else -> a regular expression."""
    if matcher in ("", "*", None):
        return True
    if re.fullmatch(r"[A-Za-z0-9_\- ,|]+", matcher):
        return tool in [m.strip() for m in re.split(r"[|,]", matcher)]
    try:
        return re.search(matcher, tool) is not None
    except re.error:
        return False


SHELL_TOOLS = ["Bash", "PowerShell"] if os.name == "nt" else ["Bash"]
for name, es in registered.items():
    if name not in KIT_HOOKS:
        continue
    for tool in SHELL_TOOLS:
        if not any(matcher_matches(e["matcher"], tool) for e in es):
            shown = ", ".join(repr(e["matcher"]) for e in es)
            report(False, f"{name} never runs for the {tool} tool: it is only under matcher {shown}. "
                          "Put it in the block whose matcher is exactly \"Bash|PowerShell\" (capital B and P). "
                          "Matchers are case-sensitive: \"bash|powershell\" matches nothing.")

# ---------------------------------------------------------------- 2. does each hook start?
print("2. Does each registered hook start the way Claude Code starts it?")
git_bash = find_git_bash() if os.name == "nt" else None
probe = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash",
                    "tool_input": {"command": "echo selftest"}, "cwd": PROJECT})
env = {**os.environ, "CLAUDE_PROJECT_DIR": PROJECT}
for e in pre:
    s = script_of(e)
    if not s:
        continue
    name = os.path.basename(s)
    if not os.path.isfile(s):
        report(False, f"{name}: the settings point to {s}, but there is no such file.")
        continue
    if isinstance(e["args"], list):  # exec form: no shell
        argv = [e["command"]] + [a.replace("${CLAUDE_PROJECT_DIR}", PROJECT) for a in e["args"]]
        how = "directly (\"args\" form, no shell)"
        exe = shutil.which(e["command"])
        if not exe:
            report(False, f"{name}: the program {e['command']!r} was not found. Install Python 3, or change "
                          "\"command\" in the settings (python on Windows, python3 on Mac/Linux, or py).")
            continue
        argv[0] = exe
    elif os.name == "nt":
        if git_bash:
            argv = [git_bash, "-c", e["command"]]
            how = "through Git Bash"
            note(f"{name} uses the one-line \"command\" form. It works while Git Bash is installed. "
                 "The \"args\" form in settings.example.windows.json works with or without Git Bash.")
        else:
            argv = ["powershell", "-NoProfile", "-Command", e["command"]]
            how = "through PowerShell (Git Bash was not found)"
    else:
        argv = ["/bin/sh", "-c", e["command"]]
        how = "through sh"
    try:
        p = subprocess.run(argv, input=probe, capture_output=True, text=True, env=env, timeout=30)
        ok = p.returncode == 0 and "Traceback" not in p.stderr and "can't open file" not in p.stderr
        detail = (p.stderr or p.stdout).strip().splitlines()[-1:] if not ok else []
    except (OSError, subprocess.SubprocessError) as ex:
        ok, detail = False, [str(ex)]
    if ok:
        report(True, f"{name} starts {how}")
    else:
        msg = f"{name} does NOT start {how}: {' '.join(detail)[:200]}. The hook is not checking anything."
        if "PowerShell" in how:
            msg += (" Depending on the Claude Code version, commands then either run unchecked or are all refused "
                    "with 'hook error'. Use the settings in settings.example.windows.json (they use \"args\" and "
                    "need no shell), or install Git for Windows.")
        else:
            msg += " Claude Code would show 'hook error' and the action would go ahead unchecked."
        report(False, msg)

# the interpreter itself: python3 on Windows can be a Microsoft Store stub that isn't Python
for prog in sorted({e["command"] if isinstance(e["args"], list) else (shlex.split(e["command"], posix=False) or [""])[0]
                    for e in pre if script_of(e)}):
    found = shutil.which(prog)
    if not found:
        continue
    extra = ["-3"] if os.path.basename(prog).lower().startswith("py") and not os.path.basename(prog).lower().startswith("python") else []
    try:
        p = subprocess.run([found] + extra + ["--version"], capture_output=True, text=True, timeout=10)
        version = (p.stdout + p.stderr).strip()
    except (OSError, subprocess.SubprocessError):
        version = ""
    report(version.startswith("Python 3"), f"{prog!r} runs {version} ({found})" if version.startswith("Python 3")
           else f"{prog!r} is not a working Python 3 ({found}). Change the program in .claude/settings.json.")

# ---------------------------------------------------------------- 3. behaviour
print("3. no_mass_delete in .claude/hooks/")

if "no_mass_delete.py" not in present:
    report(False, "no_mass_delete.py is not in .claude/hooks/. Copy it there from the hooks/ folder of this repository.")
else:
    report(decision(run("no_mass_delete.py", shell("rm -rf build"))) == "deny",
           "no_mass_delete blocks `rm -rf build` (Bash)")
    report(decision(run("no_mass_delete.py", shell("Remove-Item -Recurse -Force .\\build", "PowerShell"))) == "deny",
           "no_mass_delete blocks `Remove-Item -Recurse` (PowerShell)")
    report(decision(run("no_mass_delete.py", shell("Remove-Item a.txt, b.txt", "PowerShell"))) == "ask",
           "no_mass_delete asks before deleting several named files")
    report(decision(run("no_mass_delete.py", shell("rm notes.txt"))) is None,
           "no_mass_delete allows deleting one file")

print()
if results and all(results):
    print("All checks passed. Now try it for real in a new Claude Code session (see README.md).")
else:
    print(f"{results.count(False) or 'Some'} check(s) failed. The hook is NOT protecting you yet. "
          "Fix the FAIL lines above, then run this again.")
sys.exit(0 if results and all(results) else 1)
