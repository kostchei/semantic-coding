"""Store Claude OAuth in Windows Credential Manager; inject only into CLI children."""
import argparse
import ctypes
import getpass
import os
import re
import shutil
import subprocess
import sys
from ctypes import wintypes

TARGET = "SemanticCoding/ClaudeCodeOAuth"


class Credential(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)), ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR),
    ]


def api():
    if os.name != "nt":
        raise RuntimeError("This credential store requires Windows")
    dll = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
    dll.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                             ctypes.POINTER(ctypes.POINTER(Credential))]
    dll.CredReadW.restype = wintypes.BOOL
    dll.CredWriteW.argtypes = [ctypes.POINTER(Credential), wintypes.DWORD]
    dll.CredWriteW.restype = wintypes.BOOL
    dll.CredFree.argtypes = [ctypes.c_void_p]
    dll.CredFree.restype = None
    return dll


def read_token():
    dll = api()
    pointer = ctypes.POINTER(Credential)()
    if not dll.CredReadW(TARGET, 1, 0, ctypes.byref(pointer)):
        error = ctypes.get_last_error()
        if error == 1168:
            return None
        raise ctypes.WinError(error)
    try:
        return ctypes.string_at(pointer.contents.CredentialBlob,
                                pointer.contents.CredentialBlobSize).decode("utf-8")
    finally:
        dll.CredFree(pointer)


def store_token(token):
    if not token or any(c.isspace() for c in token):
        raise ValueError("Expected a nonempty token without whitespace")
    blob = token.encode("utf-8")
    if len(blob) > 2560:
        raise ValueError("Token exceeds Windows generic credential size limit")
    buffer = ctypes.create_string_buffer(blob)
    credential = Credential()
    credential.Type = 1
    credential.TargetName = TARGET
    credential.CredentialBlobSize = len(blob)
    credential.CredentialBlob = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))
    credential.Persist = 2  # Persists for this Windows user on this machine.
    credential.UserName = "Claude Code OAuth"
    dll = api()
    if not dll.CredWriteW(ctypes.byref(credential), 0):
        raise ctypes.WinError(ctypes.get_last_error())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["store", "setup", "status", "run"])
    parser.add_argument("--cli")
    args, remaining = parser.parse_known_args()
    if args.action == "store":
        if remaining or not sys.stdin.isatty():
            parser.error("Use an interactive terminal for hidden token entry; never pass a token as an argument")
        store_token(getpass.getpass("Claude setup-token (hidden): ").strip())
        print("Saved in Windows Credential Manager.")
        return 0
    if args.action == "setup":
        if not args.cli or remaining or not sys.stdin.isatty():
            parser.error("Run setup in an interactive terminal with --cli pointing to the Claude native executable")
        # setup-token returns an inference token without saving CLI credentials.
        # Show only its official authorization URL; never echo its token output.
        process = subprocess.Popen([args.cli, "setup-token"], stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                   errors="replace")
        output = []
        announced = False
        for line in process.stdout:
            output.append(line)
            if not announced and 'oauth/authorize?' in line:
                print("Complete Claude Code authorization in the browser opened by the CLI.", flush=True)
                announced = True
        if process.wait() != 0:
            print("Claude token setup failed; no credential was stored.", file=sys.stderr)
            return 1
        tokens = re.findall(r'sk-ant-oat01-[A-Za-z0-9_-]+', ''.join(output))
        if not tokens:
            print("No OAuth token found in setup output; no credential was stored.", file=sys.stderr)
            return 1
        store_token(tokens[-1])
        print("Claude OAuth saved in Windows Credential Manager; token output suppressed.")
        return 0
    token = read_token()
    if args.action == "status":
        print("Stored Claude OAuth credential: " + ("present" if token else "absent"))
        return 0 if token else 1
    if not args.cli:
        parser.error("run requires --cli")
    environment = os.environ.copy()
    if token and not any(environment.get(key) for key in
                         ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")):
        environment["CLAUDE_CODE_OAUTH_TOKEN"] = token
    command = [args.cli]
    if args.cli.lower().endswith(".ps1"):
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if not shell:
            parser.error("PowerShell is required for this CLI launcher")
        command = [shell, "-NoProfile", "-File", args.cli]
    if remaining[:1] == ["--"]:
        remaining = remaining[1:]
    return subprocess.call(command + remaining, env=environment)


if __name__ == "__main__":
    raise SystemExit(main())
