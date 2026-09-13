import ctypes
import contextlib
import io
import os
import sys
import unittest
import uuid
from unittest.mock import patch, Mock

import secure_credentials as credentials


class CredentialTests(unittest.TestCase):
    def test_setup_suppresses_token_output(self):
        fake_token = 'sk-ant-oat01-test-only-not-a-real-token'
        child = Mock(stdout=iter(['https://claude.com/oauth/authorize?example\n', fake_token + '\n']))
        child.wait.return_value = 0
        output = io.StringIO()
        with patch.object(sys, 'argv', ['credentials', 'setup', '--cli', 'claude.exe']), \
             patch.object(sys.stdin, 'isatty', return_value=True), \
             patch.object(credentials.subprocess, 'Popen', return_value=child), \
             patch.object(credentials, 'store_token') as save, contextlib.redirect_stdout(output):
            self.assertEqual(credentials.main(), 0)
        save.assert_called_once_with(fake_token)
        self.assertNotIn(fake_token, output.getvalue())

    @unittest.skipUnless(os.name == 'nt', 'Windows Credential Manager required')
    def test_windows_store_round_trip(self):
        # A unique test-only target never touches the user's Claude credential.
        target = 'SemanticCoding/Test/' + uuid.uuid4().hex
        with patch.object(credentials, 'TARGET', target):
            try:
                self.assertIsNone(credentials.read_token())
                credentials.store_token('test-only-not-an-auth-token')
                self.assertEqual(credentials.read_token(), 'test-only-not-an-auth-token')
            finally:
                dll = credentials.api()
                dll.CredDeleteW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32]
                dll.CredDeleteW.restype = ctypes.c_int
                dll.CredDeleteW(target, 1, 0)

    def test_child_gets_credential_without_parent_environment_mutation(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(sys, 'argv', ['credentials', 'run', '--cli', 'claude.exe', '--', '-p']), \
             patch.object(credentials, 'read_token', return_value='test-token'), \
             patch.object(credentials.subprocess, 'call', return_value=0) as launch:
            self.assertEqual(credentials.main(), 0)
            self.assertEqual(launch.call_args.kwargs['env']['CLAUDE_CODE_OAUTH_TOKEN'], 'test-token')
            self.assertEqual(launch.call_args.args[0], ['claude.exe', '-p'])
            self.assertNotIn('CLAUDE_CODE_OAUTH_TOKEN', os.environ)

    def test_explicit_credentials_keep_precedence(self):
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'}, clear=True), \
             patch.object(sys, 'argv', ['credentials', 'run', '--cli', 'claude.exe']), \
             patch.object(credentials, 'read_token', return_value='stored-token'), \
             patch.object(credentials.subprocess, 'call', return_value=0) as launch:
            credentials.main()
            self.assertNotIn('CLAUDE_CODE_OAUTH_TOKEN', launch.call_args.kwargs['env'])


if __name__ == '__main__':
    unittest.main()
