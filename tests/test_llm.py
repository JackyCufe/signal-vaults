import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from signal_vaults import llm


class CodexBackendTests(unittest.TestCase):
    def test_codex_chat_uses_ephemeral_read_only_exec(self):
        def fake_run(cmd, **kwargs):
            output_path = Path(cmd[cmd.index("--output-last-message") + 1])
            output_path.write_text('{"knowledge": []}', encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "progress", "")

        with patch.object(llm, "_codex_command", return_value=["codex"]), \
                patch.object(llm.subprocess, "run", side_effect=fake_run) as run:
            result = llm.codex_chat("[chat data]", "return JSON", timeout=3)

        self.assertEqual(result, '{"knowledge": []}')
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[:2], ["codex", "exec"])
        self.assertIn("--ephemeral", cmd)
        self.assertIn("--sandbox", cmd)
        self.assertIn("read-only", cmd)
        self.assertIn("--skip-git-repo-check", cmd)
        self.assertIn("--output-last-message", cmd)
        self.assertTrue(run.call_args.kwargs["cwd"])

    def test_codex_failure_does_not_expose_input(self):
        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 7, "", "auth failed")

        with patch.object(llm, "_codex_command", return_value=["codex"]), \
                patch.object(llm.subprocess, "run", side_effect=fake_run):
            with self.assertRaisesRegex(RuntimeError, "Codex exec 失败") as caught:
                llm.codex_chat("PRIVATE_CHAT_TEXT", "PRIVATE_SYSTEM", timeout=3)
        self.assertNotIn("PRIVATE_CHAT_TEXT", str(caught.exception))
        self.assertNotIn("PRIVATE_SYSTEM", str(caught.exception))

    def test_child_environment_removes_local_secrets(self):
        with patch.dict(llm.os.environ, {
            "DISCORD_BOT_TOKEN": "secret",
            "DISCORD_CHANNEL_ID": "channel",
            "HERMES_DB_DIR": "private-db",
            "LLM_API_KEY": "api-secret",
            "CODEX_ACCESS_TOKEN": "keep-for-codex",
        }, clear=False):
            env = llm._codex_child_env()
        self.assertNotIn("DISCORD_BOT_TOKEN", env)
        self.assertNotIn("DISCORD_CHANNEL_ID", env)
        self.assertNotIn("HERMES_DB_DIR", env)
        self.assertNotIn("LLM_API_KEY", env)
        self.assertEqual(env["CODEX_ACCESS_TOKEN"], "keep-for-codex")

    def test_backend_prefers_codex_when_auto_has_no_api_key(self):
        with patch.object(llm.config, "LLM_BACKEND", "auto"), \
                patch.object(llm.config, "LLM_API_KEY", ""), \
                patch.object(llm, "codex_available", return_value=True):
            self.assertEqual(llm.backend(), "codex")

    def test_windows_path_candidate_is_supported(self):
        with patch.object(llm.config, "CODEX_BIN", ""), \
                patch.object(llm.os, "name", "nt"), \
                patch.object(llm.os, "environ", {"LOCALAPPDATA": "C:\\LocalAppData"}), \
                patch.object(llm.Path, "glob", return_value=[Path("C:\\Codex\\codex.exe")]), \
                patch.object(llm.Path, "stat"), \
                patch.object(llm.os.path, "isfile", return_value=True), \
                patch.object(llm.shutil, "which", return_value=None):
            self.assertEqual(llm._codex_command(), ["C:\\Codex\\codex.exe"])


if __name__ == "__main__":
    unittest.main()
