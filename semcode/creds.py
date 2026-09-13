"""Windows Credential Manager single-source reader and writer for grepai and agent harnesses."""

import argparse
import ctypes
from ctypes import wintypes
import getpass
import os
import sys
from typing import Optional

TARGET_LMSTUDIO = "grepai-hybrid/lmstudio"
TARGET_LMSTUDIO_LEGACY = "PraetorSilica/LMStudioDev"
TARGET_CLAUDE = "SemanticCoding/ClaudeCodeOAuth"


class CredentialMissing(RuntimeError):
    """Raised when a required credential is not found in Windows Credential Manager."""
    pass


class Credential(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


def _get_advapi32():
    if os.name != "nt":
        raise NotImplementedError("Windows Credential Manager is only supported on Windows (os.name == 'nt')")
    dll = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
    dll.CredReadW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.POINTER(Credential)),
    ]
    dll.CredReadW.restype = wintypes.BOOL
    dll.CredWriteW.argtypes = [ctypes.POINTER(Credential), wintypes.DWORD]
    dll.CredWriteW.restype = wintypes.BOOL
    dll.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    dll.CredDeleteW.restype = wintypes.BOOL
    dll.CredFree.argtypes = [ctypes.c_void_p]
    dll.CredFree.restype = None
    return dll


def _decode_blob(blob: bytes) -> str:
    """Safely decode credential blob supporting both UTF-8 and UTF-16LE."""
    if b"\x00" in blob:
        # Likely UTF-16LE (e.g. written by cmdkey or Windows native credential UI)
        try:
            return blob.decode("utf-16le").strip("\x00 \t\r\n")
        except UnicodeDecodeError:
            return blob.decode("utf-8", errors="replace").strip("\x00 \t\r\n")
    else:
        # Likely UTF-8 (e.g. written by standard Python/OpenSSL/OAuth scripts)
        try:
            return blob.decode("utf-8").strip("\x00 \t\r\n")
        except UnicodeDecodeError:
            return blob.decode("utf-16le", errors="replace").strip("\x00 \t\r\n")


def read_credential(target: str) -> Optional[str]:
    """Read a credential from Windows Credential Manager. Returns None if not found."""
    dll = _get_advapi32()
    pointer = ctypes.POINTER(Credential)()
    if not dll.CredReadW(target, 1, 0, ctypes.byref(pointer)):
        error = ctypes.get_last_error()
        if error == 1168:  # ERROR_NOT_FOUND
            return None
        raise ctypes.WinError(error)
    try:
        blob = ctypes.string_at(pointer.contents.CredentialBlob, pointer.contents.CredentialBlobSize)
        return _decode_blob(blob)
    finally:
        dll.CredFree(pointer)


def store_credential(target: str, token: str, user_name: str = "grepai") -> None:
    """Store a generic credential in Windows Credential Manager."""
    if not token or any(c.isspace() for c in token):
        raise ValueError("Expected a non-empty token without whitespace")
    blob = token.encode("utf-8")
    if len(blob) > 2560:
        raise ValueError("Token exceeds Windows generic credential size limit")
    buffer = ctypes.create_string_buffer(blob)
    credential = Credential()
    credential.Type = 1  # CRED_TYPE_GENERIC
    credential.TargetName = target
    credential.CredentialBlobSize = len(blob)
    credential.CredentialBlob = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))
    credential.Persist = 2  # CRED_PERSIST_LOCAL_MACHINE (persists for user on this machine)
    credential.UserName = user_name

    dll = _get_advapi32()
    if not dll.CredWriteW(ctypes.byref(credential), 0):
        raise ctypes.WinError(ctypes.get_last_error())


def delete_credential(target: str) -> bool:
    """Delete a credential from Windows Credential Manager. Returns True if deleted or False if not found."""
    dll = _get_advapi32()
    if not dll.CredDeleteW(target, 1, 0):
        error = ctypes.get_last_error()
        if error == 1168:
            return False
        raise ctypes.WinError(error)
    return True


def get_lmstudio_token() -> str:
    """Retrieve LM Studio auth token. Raises CredentialMissing if absent."""
    token = read_credential(TARGET_LMSTUDIO)
    if token:
        return token

    # Auto-migration fallback for existing installation:
    # If legacy PraetorSilica/LMStudioDev is present, migrate it automatically to grepai-hybrid/lmstudio
    legacy_token = read_credential(TARGET_LMSTUDIO_LEGACY)
    if legacy_token:
        store_credential(TARGET_LMSTUDIO, legacy_token, user_name="lmstudio")
        return legacy_token

    raise CredentialMissing(
        f"Credential '{TARGET_LMSTUDIO}' not found in Windows Credential Manager.\n"
        f"Remediation: Run `cmdkey /generic:{TARGET_LMSTUDIO} /user:lmstudio /pass` "
        f"or `python -m semcode.creds set lmstudio` to store your LM Studio token."
    )


def get_claude_token() -> Optional[str]:
    """Retrieve Claude OAuth token, or None if absent."""
    return read_credential(TARGET_CLAUDE)


def main():
    parser = argparse.ArgumentParser(description="Manage credentials in Windows Credential Manager")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    set_parser = subparsers.add_parser("set", help="Set a credential interactively")
    set_parser.add_argument("target_type", choices=["lmstudio", "claude"])

    get_parser = subparsers.add_parser("get", help="Check status of a credential")
    get_parser.add_argument("target_type", choices=["lmstudio", "claude"])

    subparsers.add_parser("status", help="Show presence of all managed credentials")

    delete_parser = subparsers.add_parser("delete", help="Delete a stored credential")
    delete_parser.add_argument("target_type", choices=["lmstudio", "legacy-lmstudio", "claude"])

    args = parser.parse_args()

    if args.subcommand == "set":
        if not sys.stdin.isatty():
            sys.exit("Error: 'set' requires an interactive terminal for secure masked input.")
        if args.target_type == "lmstudio":
            val = getpass.getpass("LM Studio token (hidden): ").strip()
            store_credential(TARGET_LMSTUDIO, val, user_name="lmstudio")
            print(f"Stored {TARGET_LMSTUDIO} successfully.")
        elif args.target_type == "claude":
            val = getpass.getpass("Claude OAuth token (hidden): ").strip()
            store_credential(TARGET_CLAUDE, val, user_name="Claude Code OAuth")
            print(f"Stored {TARGET_CLAUDE} successfully.")

    elif args.subcommand == "get":
        if args.target_type == "lmstudio":
            token = get_lmstudio_token()
            print(f"{TARGET_LMSTUDIO}: present (length {len(token)})")
        elif args.target_type == "claude":
            token = get_claude_token()
            print(f"{TARGET_CLAUDE}: {'present' if token else 'absent'}")

    elif args.subcommand == "status":
        lm = read_credential(TARGET_LMSTUDIO)
        lm_leg = read_credential(TARGET_LMSTUDIO_LEGACY)
        cl = read_credential(TARGET_CLAUDE)
        print(f"{TARGET_LMSTUDIO}: {'present' if lm else 'absent'}")
        print(f"{TARGET_LMSTUDIO_LEGACY}: {'present' if lm_leg else 'absent'}")
        print(f"{TARGET_CLAUDE}: {'present' if cl else 'absent'}")

    elif args.subcommand == "delete":
        target = {
            "lmstudio": TARGET_LMSTUDIO,
            "legacy-lmstudio": TARGET_LMSTUDIO_LEGACY,
            "claude": TARGET_CLAUDE,
        }[args.target_type]
        deleted = delete_credential(target)
        print(f"Deleted {target}: {deleted}")


if __name__ == "__main__":
    main()
