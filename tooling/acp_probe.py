"""Exercise ACP initialize/session creation only; never send a model prompt."""
import json
import os
from pathlib import Path
import selectors
import subprocess
import tempfile
import time


def probe_session(launcher, cwd, env, timeout=30):
    # Bound stderr in a temporary file rather than mixing it with protocol JSON.
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen([str(launcher)], cwd=cwd, env=env,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors)
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        buffer = b''
        deadline = time.monotonic() + timeout
        methods = []

        def request(identifier, method, params):
            nonlocal buffer
            methods.append(method)
            payload = {'jsonrpc': '2.0', 'id': identifier, 'method': method, 'params': params}
            process.stdin.write((json.dumps(payload) + '\n').encode())
            process.stdin.flush()
            while time.monotonic() < deadline:
                if not selector.select(timeout=min(1, max(0, deadline - time.monotonic()))):
                    if process.poll() is not None:
                        raise RuntimeError('ACP exited before returning ' + method)
                    continue
                chunk = os.read(process.stdout.fileno(), 65536)
                if not chunk:
                    raise RuntimeError('ACP closed its output before returning ' + method)
                buffer += chunk
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    if not line.strip():
                        continue
                    message = json.loads(line)
                    if message.get('id') != identifier or 'method' in message:
                        continue
                    if 'error' in message:
                        # Do not print arbitrary protocol payloads or authentication material.
                        raise RuntimeError('ACP {} failed (code {}); check local login/connectivity'.format(
                            method, message['error'].get('code', 'unknown')))
                    return message['result']
            raise RuntimeError('ACP timed out during ' + method)

        try:
            request(1, 'initialize', {'protocolVersion': 1, 'clientCapabilities': {},
                                     'clientInfo': {'name': 'dotfiles-validation', 'version': '1'}})
            result = request(2, 'session/new', {'cwd': str(Path(cwd).resolve()), 'mcpServers': []})
            if not result.get('sessionId'):
                raise RuntimeError('ACP session/new returned no session ID')
            return {'initialize': 'passed', 'session_creation': 'passed',
                    'methods_sent': methods, 'model_prompts_sent': 0}
        finally:
            selector.close()
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            process.stdin.close()
            process.stdout.close()
