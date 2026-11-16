#!/usr/bin/env python3
# Part of claude-code-safety-starter, the free edition of the Claude Code Safety Kit for Non-Programmers. (c) 2026 LGA. MIT License; see LICENSE.
"""PreToolUse hook (matcher: Bash|PowerShell): stop commands that can delete many files at once,
and ask you first when one command deletes several named files.

What it blocks
- recursive deletes: rm -r / -rf / -fr / -R / --recursive, Remove-Item -Recurse (and the
  PowerShell aliases rm, ri, del, erase, rd, rmdir), rd /s, rmdir /s, del /s
- deletes with a wildcard (* or ?): rm *.txt, del /q *.log, Remove-Item .\\build\\*
- del / erase / Remove-Item on a folder (cmd's `del /q dist` deletes every file in dist):
  a name that ends with \\ or /, or that is an existing folder in the folder Claude works in
- Remove-Item with -Include / -Exclude / -Filter, or fed by a pipe (Get-ChildItem | Remove-Item)
- a delete inside a loop (for / foreach / ForEach-Object / xargs)
- git clean -f (git clean -n / --dry-run is allowed)
- find ... -delete, find ... -exec rm
- python with shutil.rmtree, node with a recursive rm, rimraf
- format C:, Format-Volume, Clear-Disk, diskpart, cipher /w, mkfs, dd of=/dev/..., robocopy /mir or /purge
- [IO.Directory]::Delete(path, $true)

What it asks you about (a Yes/No question, not a block)
- one command that names two or more files or folders: rm a.txt b.txt, rm -f a b c, del a.txt b.txt,
  Remove-Item a.txt, b.txt, Remove-Item -Path a.txt,b.txt, git rm a.txt b.txt
  (in a non-interactive run, `claude -p`, nobody can answer, so Claude Code refuses it)

It also looks inside bash -c "...", cmd /c ... (and cmd //c from Git Bash), powershell -Command "...",
pwsh -c, Invoke-Expression, eval, Start-Process, `...`, and npx / pnpm dlx / bunx (npx rimraf, npx shx rm -rf).
It asks first when the list of files comes from another command: Remove-Item (Get-ChildItem ...), rm $(cat list).

What it lets through
- deleting one named file: rm notes.txt, Remove-Item .\\a.txt, del old.log
- text that only mentions a delete: echo "rm -rf", git commit -m "remove rm -rf"
- git rm --cached, git rm one-file.txt, rmdir emptyfolder (bash), git clean -n

A guard rail, not a guarantee: there are other ways to delete files that it does not see.
Keep a backup (see README.md). Standard library only. Bad input -> does nothing.
"""
import json
import os
import re
import shlex
import sys

SEP = set(";&|()\n{}")
WRAPPERS = {"sudo", "command", "exec", "nohup", "time", "env", "doas", "builtin", "then", "do", "else",
            "elif", "!", "$", "@", "&", "call", "-not", "wsl", "busybox", "shx"}
RUNNERS = {"npx", "pnpx", "bunx"}            # npx rimraf, bunx shx rm -rf
RUNNER_SUBCOMMANDS = {"pnpm": ("dlx", "exec"), "yarn": ("dlx", "exec"), "npm": ("exec",)}
CMD_SWITCH = re.compile(r"(?i)(?:^|\s)/{1,2}[ckr](?:\s+|$)(.*)", re.S)   # cmd /c ... and Git Bash's cmd //c ...
PS_COMMAND = re.compile(r"(?i)(?:^|\s)-c(?:o(?:m(?:m(?:a(?:n(?:d)?)?)?)?)?)?\s+(.*)", re.S)

PS_VALUE_OPTS = {"executionpolicy", "ep", "ex", "windowstyle", "w", "win", "version", "v", "inputformat", "if",
                 "outputformat", "of", "configurationname", "config", "workingdirectory", "wd", "settingsfile",
                 "custompipename", "psconsolefile"}


def ps_inner(args):
    """The command a powershell / pwsh call runs: after -Command, or the first word that is not an option
    (Windows PowerShell runs `powershell "Remove-Item x"` as a command). None for -File / -EncodedCommand."""
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("-") and " " not in a and len(a) > 1:
            p = a[1:].split(":", 1)[0].lower()
            if p and "command".startswith(p) and (len(p) == 1 or len(p) >= 3):  # -c, -com, -Command
                return " ".join(args[i + 1:]) or None
            if p in ("file", "f", "encodedcommand", "enc", "e", "ec") or (len(p) >= 3 and "encodedcommand".startswith(p)):
                return None
            i += 2 if p in PS_VALUE_OPTS else 1
            continue
        break
    return " ".join(args[i:]) or None

CWD = ""  # the folder Claude Code says the command runs in (set in main)


def is_folder(name):
    """True when `name` is a folder: it ends with \\ or /, or it exists as a folder. False when unknown."""
    n = name.strip("'\"")
    if not n or "$" in n or "%" in n:
        return False
    if n.endswith(("\\", "/")) and n not in ("\\", "/"):
        return True
    try:
        return os.path.isdir(os.path.join(CWD or os.getcwd(), os.path.expanduser(n)))
    except (OSError, ValueError):
        return False

LOOPS = {"for", "foreach", "foreach-object", "%", "while", "until", "xargs", "parallel"}
DELETE_NAMES = {"rm", "remove-item", "ri", "del", "erase", "rd", "rmdir", "unlink"}
PS_DELETE_NAMES = {"remove-item", "ri", "rm", "del", "erase", "rd", "rmdir"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "git-bash"}
POWERSHELLS = {"powershell", "pwsh"}


def tokenize(line):
    """Split a command line into tokens. Quotes are respected; backslashes are kept (Windows paths)."""
    try:
        lx = shlex.shlex(line, posix=True, punctuation_chars=";&|()\n")
        lx.whitespace = " \t\r"
        lx.whitespace_split = True
        lx.escape = ""
        lx.commenters = ""
        return list(lx)
    except ValueError:
        return re.findall(r"[;&|()\n]+|[^\s;&|()]+", line)


def split_commands(line):
    """Return [(separator_before, tokens)] for each simple command in the line."""
    out, cur, sep, comment = [], [], "", False
    for tok in tokenize(line):
        # split PowerShell braces glued to words: {Remove-Item ... }
        parts = []
        while len(tok) > 1 and tok[0] == "{":
            parts.append("{")
            tok = tok[1:]
        tail = []
        while len(tok) > 1 and tok[-1] == "}":
            tail.append("}")
            tok = tok[:-1]
        for t in parts + [tok] + tail:
            if comment:
                if "\n" in t:
                    comment = False
                    sep = "\n"
                continue
            if t.startswith("#") and not cur:
                comment = True
                continue
            if t and set(t) <= SEP:
                if cur:
                    out.append((sep, cur))
                cur, sep = [], t
            else:
                cur.append(t)
    if cur:
        out.append((sep, cur))
    return out


def norm(name):
    name = os.path.basename(name.replace("\\", "/")).lower()
    for ext in (".exe", ".cmd", ".bat", ".com"):
        if name.endswith(ext):
            name = name[: -len(ext)]
    return name


def is_slash_flag(t):
    """/s, /q, /a:h and switches written together like /S/Q"""
    return bool(re.fullmatch(r"(?:/[A-Za-z?](:[^/]*)?)+", t))


def ps_param(t):
    """'-Recurse:$true' -> 'recurse' ; not a param -> None"""
    m = re.fullmatch(r"-([A-Za-z][\w-]*)(:.*)?", t)
    return m.group(1).lower() if m else None


PS_SWITCHES = ("recurse", "force", "whatif", "confirm", "verbose", "debug")
PS_FILTERS = ("include", "exclude", "filter")
PS_PATHS = ("path", "literalpath")
REDIRECT = re.compile(r"(?:\d|\*|&)?>>?(.*)")


def ask(what):
    return ("ask", what)


def check_delete(name, args, mode, sep, in_loop, sep_after=""):
    """Return None, a reason to deny (str), or ask(reason) for a plain list of several names."""
    names, recursive, filtered = [], False, False
    ps_style = mode == "ps" or name in ("remove-item", "ri")
    end_opts = False
    i = 0
    while i < len(args):
        a = args[i]
        i += 1
        m = REDIRECT.fullmatch(a)
        if m and not end_opts:
            if not m.group(1):
                i += 1  # the redirect target is the next word
            continue
        if not end_opts and a == "--":
            end_opts = True
            continue
        if not end_opts and is_slash_flag(a) and name in ("del", "erase", "rd", "rmdir"):
            if re.search(r"(?i)/s(?![a-z])", a):
                recursive = True
            continue
        if not end_opts and a.startswith("-") and len(a) > 1:
            if ps_style:
                p = ps_param(a) or ""
                value = a.split(":", 1)[1] if ":" in a else None
                if not p:
                    continue
                if len(p) >= 2 and any(w.startswith(p) for w in PS_FILTERS):
                    filtered = True
                    if value is None:
                        i += 1
                    continue
                if any(w.startswith(p) for w in PS_SWITCHES) or p in ("rf", "fr"):
                    if "recurse".startswith(p) or p in ("rf", "fr"):
                        recursive = recursive or (value or "").lower() != "$false"
                    continue
                if value is None and i < len(args):
                    value = args[i]
                    i += 1
                if any(w.startswith(p) for w in PS_PATHS) and value:
                    names += [v for v in value.split(",") if v]
                continue
            if a == "--recursive" or (not a.startswith("--") and re.search(r"[rR]", a)):
                recursive = True
            continue
        if ps_style:
            names += [v for v in a.split(",") if v]
        else:
            names.append(a)
    if name in ("rmdir", "rd") and mode == "sh" and not recursive:
        return None  # bash rmdir only removes empty folders
    if recursive:
        return "a recursive delete (it removes a folder and everything inside it)"
    if any(("*" in a or "?" in a) for a in names):
        return "a delete with a wildcard (* or ?), which can match many files"
    if filtered:
        return "a delete with -Include/-Exclude/-Filter, which can match many files"
    if sep == "|" and ps_style:
        return "a delete that removes everything piped into it"
    if in_loop:
        return "a delete inside a loop, which can remove many files"
    folder_delete = name in ("del", "erase") or (ps_style and name in ("remove-item", "ri", "rm", "del", "erase"))
    if folder_delete:
        for n in names:
            if is_folder(n):
                return (f"a delete of the folder {n.strip(chr(39) + chr(34))}, which removes every file inside it "
                        "(del and Remove-Item on a folder take all of its files)")
    if any(n in ("$", "@") for n in names) or (not names and sep_after.startswith("(")):
        return ask("the list of files to delete comes from another command, so it can be any number of files")
    if len(names) >= 2:
        shown = ", ".join(names[:8]) + (", ..." if len(names) > 8 else "")
        return ask(f"it deletes {len(names)} files or folders in one command: {shown}")
    return None


def check_command(tokens, mode, sep, in_loop, line, depth, sep_after=""):
    while tokens and (re.fullmatch(r"\w+=.*", tokens[0]) or tokens[0].lower() in WRAPPERS):
        tokens = tokens[1:]
    if not tokens:
        return None
    name, args = norm(tokens[0]), tokens[1:]

    # npx rimraf, pnpm dlx shx rm -rf, ...
    if name in RUNNERS or (name in RUNNER_SUBCOMMANDS and args and args[0] in RUNNER_SUBCOMMANDS[name]):
        rest = args if name in RUNNERS else args[1:]
        rest = list(rest)
        while rest and rest[0].startswith("-"):  # npx -y / --yes
            rest.pop(0)
        if rest:
            rest[0] = re.sub(r"(?<=.)@[^/]*$", "", rest[0])  # rimraf@5 -> rimraf
            return check_command(rest, mode, sep, in_loop, line, depth, sep_after)
        return None

    # nested command lines
    if depth < 4:
        nested = None
        if name in SHELLS:
            for i, a in enumerate(args):
                if re.fullmatch(r"-[a-z]*c[a-z]*", a) and i + 1 < len(args):
                    nested = (args[i + 1], "sh")
                    break
        elif name == "cmd":
            m = CMD_SWITCH.search(" ".join(args))
            nested = (m.group(1), "cmd") if m else None
        elif name in POWERSHELLS:
            inner = ps_inner(args)
            nested = (inner, "ps") if inner else None
        elif name in ("invoke-expression", "iex") and args:
            nested = (" ".join(a for a in args if not a.lower().startswith("-command")), "ps")
        elif name == "eval" and args:
            nested = (" ".join(args), "sh")
        elif name in ("start-process", "saps", "start") and args:
            nested = (" ".join(a for a in args if not (a.startswith("-") and " " not in a) and not is_slash_flag(a)).replace(",", " "), mode)
        if nested:
            return check_line(nested[0], nested[1], depth + 1)

    if name in DELETE_NAMES:
        return check_delete(name, args, "ps" if (mode == "ps" and name in PS_DELETE_NAMES) else
                            ("cmd" if mode == "cmd" else mode), sep, in_loop, sep_after)
    if name == "git":
        i = 0
        while i < len(args) and args[i].startswith("-"):
            i += 2 if args[i] in ("-C", "-c") else 1
        if i < len(args) and args[i] == "rm":
            rest = args[i + 1:]
            if "--cached" in rest:
                return None  # only stops tracking; the files stay on disk
            return check_delete("rm", [a for a in rest if a not in ("-f", "--force", "-q", "--quiet")], "sh", sep, in_loop)
        if i < len(args) and args[i] == "clean":
            flags = [a for a in args[i + 1:] if a.startswith("-")]
            dry = any(f in ("--dry-run",) or (not f.startswith("--") and "n" in f) for f in flags)
            force = any(f == "--force" or (not f.startswith("--") and "f" in f) for f in flags)
            if force and not dry:
                return "git clean -f (deletes every file git is not tracking)"
        return None
    if name == "find":
        low = [a.lower() for a in args]
        if "-delete" in low:
            return "find -delete (deletes every file that matches)"
        for i, a in enumerate(low):
            if a in ("-exec", "-execdir", "-ok", "-okdir") and i + 1 < len(low) and norm(low[i + 1]) in DELETE_NAMES:
                return "find -exec rm (deletes every file that matches)"
        return None
    if name == "xargs":
        if any(norm(a) in DELETE_NAMES for a in args):
            return "xargs rm (deletes every file in the list)"
        return None
    if name in ("python", "python3", "py", "pythonw") and "rmtree" in line:
        return "shutil.rmtree (deletes a folder and everything inside it)"
    if name in ("node", "deno", "bun") and re.search(r"rmSync|rmdirSync|fs\.rm\(|\.rm\(", line) and "recursive" in line:
        return "a recursive delete in Node.js"
    if name == "rimraf" or (name in ("npx", "pnpx", "bunx") and any(norm(a) == "rimraf" for a in args)):
        return "rimraf (deletes a folder and everything inside it)"
    if name == "format" and any(re.fullmatch(r"[A-Za-z]:\\?", a) for a in args):
        return "formatting a drive"
    if name in ("format-volume", "clear-disk", "initialize-disk", "remove-partition", "diskpart") or name.startswith("mkfs"):
        return "erasing a disk or partition"
    if name == "cipher" and any(a.lower().startswith("/w") for a in args):
        return "cipher /w (wipes free space on a drive)"
    if name == "dd" and any(a.lower().startswith("of=/dev/") for a in args):
        return "dd writing to a raw disk"
    if name == "robocopy" and any(a.lower() in ("/mir", "/purge") for a in args):
        return "robocopy /mir or /purge (deletes files in the destination)"
    return None


def check_line(line, mode, depth=0):
    """Return None, a deny reason (str) or ask(reason). A deny anywhere in the line wins."""
    line = line.replace("–", "-").replace("—", "-")  # PowerShell accepts en/em dashes as '-'
    if re.search(r"\[(?:System\.)?IO\.Directory\]::Delete\s*\([^)]*,\s*(?:\$true|1)\s*\)", line, re.I):
        return "[IO.Directory]::Delete with recursion"
    if re.search(r"(?i)\b(?:get-childitem|gci|ls|dir)\b.*\.Delete\s*\(", line, re.S):
        return "a .Delete() call on a list of files"
    asked = None
    if depth < 4 and mode != "ps":
        for inner in re.findall(r"`([^`]+)`", line):  # bash command substitution `...`
            what = check_line(inner, mode, depth + 1)
            if isinstance(what, str):
                return what
            asked = asked or what
    in_loop = False
    cmds = split_commands(line)
    for k, (sep, tokens) in enumerate(cmds):
        first = tokens[0].lower() if tokens else ""
        sep_after = cmds[k + 1][0] if k + 1 < len(cmds) else ""
        what = check_command(tokens, mode, sep, in_loop, line, depth, sep_after)
        if isinstance(what, str):
            return what
        if what and not asked:
            asked = what
        if first in LOOPS or norm(first) in LOOPS:
            in_loop = True
    return asked


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    if not isinstance(data, dict):
        return 0
    tool = data.get("tool_name")
    if tool not in ("Bash", "PowerShell"):
        return 0
    line = (data.get("tool_input") or {}).get("command") or ""
    if not isinstance(line, str):
        return 0
    global CWD
    CWD = data.get("cwd") if isinstance(data.get("cwd"), str) else ""
    what = check_line(line, "ps" if tool == "PowerShell" else "sh")
    if isinstance(what, tuple):
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": (
                    f"Safety check (no_mass_delete hook): {what[1]}. Files deleted this way usually skip the "
                    "Recycle Bin. Choose Yes only if this is exactly the list you want to delete. "
                    "If this is refused: do not try another way to delete them (one at a time, or with a "
                    "different command). Tell the user which files you wanted to delete and why, and let them "
                    "delete these themselves if they agree."
                ),
            }
        }))
    elif what:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"Blocked by the no_mass_delete safety hook: this command is {what}. "
                    "Files deleted this way usually skip the Recycle Bin and may be impossible to get back. "
                    "This hook blocks such commands every time, even if the user says yes, so do not offer to "
                    "run it again, do not suggest turning the hook off, and do not try another way to delete them: do not list the file names in one "
                    "command and do not delete them one at a time. Tell the user, in plain words, which "
                    "files or folders you wanted to delete and why, and ask them to delete these themselves if "
                    "they agree (for example in File Explorer, which uses the Recycle Bin)."
                ),
            }
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
