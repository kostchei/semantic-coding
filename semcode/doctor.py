"""End-to-end system diagnostic and doctor suite for semcode."""

import json
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
USER_HOME = Path.home()


class DoctorSuite:
    def __init__(self):
        self.results: List[Tuple[str, bool, str, str]] = []

    def report(self, name: str, passed: bool, detail: str = "", remediation: str = ""):
        self.results.append((name, passed, detail, remediation))
        status = "[PASS]" if passed else "[FAIL]"
        color = "\033[92m" if passed else "\033[91m"
        reset = "\033[0m"
        print(f" {color}{status}{reset} {name}")
        if detail:
            print(f"        {detail}")
        if not passed and remediation:
            print(f"        \033[96mRemediation: {remediation}\033[0m")

    def run_all(self) -> bool:
        print("=" * 68)
        print("             semcode System Doctor & Diagnostics            ")
        print("=" * 68)

        # 1. Python imports
        try:
            import mcp
            import semcode.pipeline as semcode_pipeline
            _ = semcode_pipeline
            mcp_info = f"mcp {getattr(mcp, '__version__', 'ready')}, semcode pipeline loaded"
            self.report("Python & semcode imports", True, f"Python {sys.version.split()[0]}, {mcp_info}")
        except Exception as exc:
            self.report("Python & semcode imports", False, str(exc), "Run `pip install -r requirements.txt`")

        # 2. grepai binary
        from semcode.grepai_runner import find_binary
        try:
            bin_path = find_binary()
            ver_proc = subprocess.run([bin_path, "version"], capture_output=True, text=True, check=True)
            self.report("grepai binary", True, f"{bin_path} ({ver_proc.stdout.strip()})")
        except Exception as exc:
            self.report("grepai binary", False, str(exc), "Ensure bin/grepai.exe exists or is on PATH")

        # 3. Windows Credential Manager
        from semcode.creds import read_credential, TARGET_LMSTUDIO, TARGET_CLAUDE
        lm_token = read_credential(TARGET_LMSTUDIO)
        claude_token = read_credential(TARGET_CLAUDE)
        self.report("LM Studio credential (semcode/lmstudio)", bool(lm_token),
                    f"Present in Windows Credential Manager (length {len(lm_token) if lm_token else 0})",
                    "Run `python -m semcode.creds set lmstudio`")
        self.report("Claude Code OAuth credential", bool(claude_token),
                    "Present in Windows Credential Manager" if claude_token else "Absent",
                    "Run `python -m semcode.creds set claude`")

        # 4. LM Studio API Reachability with Auth
        from semcode.creds import get_lmstudio_token
        try:
            tok = get_lmstudio_token()
            req = urllib.request.Request(
                "http://127.0.0.1:1234/v1/models",
                headers={"Authorization": f"Bearer {tok}"}
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                models = [m.get("id") for m in data.get("data", [])]
                has_text = any("nomic-embed-text" in m for m in models)
                has_code = any("nomic-embed-code" in m for m in models)
                detail = f"{len(models)} models loaded (text embedder: {has_text}, code embedder: {has_code})"
                self.report("LM Studio API reachable with auth", resp.status == 200, detail)
        except Exception as exc:
            self.report("LM Studio API reachable with auth", False, str(exc),
                        "Ensure LM Studio is running on 127.0.0.1:1234 with valid token")

        # 5. Plaintext Secrets Check
        configs = list(REPO_ROOT.glob("**/.grepai/config.yaml"))
        leaks = []
        for p in configs:
            content = p.read_text(encoding="utf-8")
            m = re.findall(r"^[ \t]*api_key:\s*['\"]?([^'\"\s]+)['\"]?", content, re.MULTILINE)
            if m:
                leaks.append(f"{p.name}: {m}")
        self.report("No plaintext secrets on disk", len(leaks) == 0,
                    f"Checked {len(configs)} config files, {len(leaks)} plaintext keys found",
                    "Strip api_key from .grepai/config.yaml files")

        # 6. Claude Code Integration
        claude_json_path = USER_HOME / ".claude.json"
        has_global_mcp = False
        no_dup_proj = True
        if claude_json_path.is_file():
            try:
                cdata = json.loads(claude_json_path.read_text(encoding="utf-8"))
                has_global_mcp = "semcode" in cdata.get("mcpServers", {})
                for pkey, pval in cdata.get("projects", {}).items():
                    if "semantic_coding" in pkey.lower():
                        if "semcode" in pval.get("mcpServers", {}):
                            no_dup_proj = False
            except Exception:
                pass
        self.report("Claude Code global MCP registration", has_global_mcp,
                    str(claude_json_path), "Run `powershell -File install_integrations.ps1`")
        self.report("Claude Code duplicate project MCP absent", no_dup_proj,
                    "No conflicting project-level entry in ~/.claude.json", "Run `powershell -File install_integrations.ps1`")

        claude_settings = USER_HOME / ".claude" / "settings.json"
        has_hook = False
        if claude_settings.is_file():
            try:
                sdata = json.loads(claude_settings.read_text(encoding="utf-8"))
                has_hook = "UserPromptSubmit" in sdata.get("hooks", {})
            except Exception:
                pass
        self.report("Claude Code prompt context hook", has_hook,
                    str(claude_settings), "Run `powershell -File install_integrations.ps1`")

        claude_md = USER_HOME / ".claude" / "CLAUDE.md"
        has_claude_block = False
        if claude_md.is_file():
            has_claude_block = "<!-- semcode:begin -->" in claude_md.read_text(encoding="utf-8")
        self.report("Claude Code global instruction block", has_claude_block,
                    str(claude_md), "Run `powershell -File install_integrations.ps1`")

        # 7. Codex Integration
        codex_md = USER_HOME / ".codex" / "AGENTS.md"
        has_codex_block = False
        if codex_md.is_file():
            has_codex_block = "<!-- semcode:begin -->" in codex_md.read_text(encoding="utf-8")
        self.report("Codex global instruction block", has_codex_block,
                    str(codex_md), "Run `powershell -File install_integrations.ps1`")

        codex_skill = USER_HOME / ".codex" / "skills" / "semcode" / "SKILL.md"
        self.report("Codex global skill", codex_skill.is_file(),
                    str(codex_skill), "Run `powershell -File install_integrations.ps1`")

        # 8. Antigravity Integration
        agy_mcp = USER_HOME / ".gemini" / "antigravity" / "mcp_config.json"
        has_agy_mcp = False
        if agy_mcp.is_file():
            try:
                adata = json.loads(agy_mcp.read_text(encoding="utf-8"))
                has_agy_mcp = "semcode" in adata.get("mcpServers", {})
            except Exception:
                pass
        self.report("Antigravity MCP server registered", has_agy_mcp,
                    str(agy_mcp), "Run `powershell -File install_integrations.ps1`")

        agy_md = USER_HOME / ".gemini" / "GEMINI.md"
        has_agy_block = False
        if agy_md.is_file():
            has_agy_block = "<!-- semcode:begin -->" in agy_md.read_text(encoding="utf-8")
        self.report("Antigravity global instruction block", has_agy_block,
                    str(agy_md), "Run `powershell -File install_integrations.ps1`")

        agy_skill = USER_HOME / ".gemini" / "config" / "skills" / "semcode" / "SKILL.md"
        self.report("Antigravity global skill", agy_skill.is_file(),
                    str(agy_skill), "Run `powershell -File install_integrations.ps1`")

        agy_stale = USER_HOME / ".gemini" / "antigravity" / "mcp" / "semcode"
        self.report("Antigravity stale descriptor removed", not agy_stale.exists(),
                    "No stale descriptor dir", f"Delete {agy_stale}")

        # 9. Registry Integrity
        from semcode.registry import load_registry
        reg_ok = False
        reg_detail = ""
        try:
            reg = load_registry()
            required_projects = ["ORAC", "ash-rpg", "LDGM", "praetor_silica"]
            missing = [p for p in required_projects if p not in reg]
            if missing:
                reg_detail = f"Missing required projects in registry: {missing}"
            else:
                reg_ok = True
                reg_detail = f"{len(reg)} registered projects: {list(reg.keys())}"
        except Exception as exc:
            reg_detail = str(exc)
        self.report("Project registry integrity", reg_ok, reg_detail, "Run `python -m semcode.sync --all`")

        # 10. Live Search Query
        from semcode.pipeline import execute_hybrid_search
        live_ok = False
        live_detail = ""
        try:
            t0 = time.perf_counter()
            res = execute_hybrid_search("mutation authority", project="ash-rpg", limit=1)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            results = res.get("results", [])
            if results:
                live_ok = True
                top = results[0]
                live_detail = f"{top.get('absolute_path')} (RRF {top.get('rrf_score', 0):.3f}, {elapsed_ms:.1f}ms)"
            else:
                live_detail = "Search returned 0 results"
        except Exception as exc:
            live_detail = str(exc)
        self.report("Live end-to-end search query", live_ok, live_detail, "Check index status with `python -m semcode.sync --all`")

        all_passed = all(r[1] for r in self.results)
        print("=" * 68)
        if all_passed:
            print(" \033[92mALL SYSTEMS OPERATIONAL - 100% HEALTHY\033[0m")
        else:
            failed_count = sum(1 for r in self.results if not r[1])
            print(f" \033[91m{failed_count} CHECK(S) FAILED - REVIEW REMEDIATION STEPS ABOVE\033[0m")
        print("=" * 68)
        return all_passed


def main():
    suite = DoctorSuite()
    success = suite.run_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
