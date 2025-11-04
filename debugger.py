#!/usr/bin/env python3
"""
Improved CTF-focused Debugger
- Selects appropriate debugger per language (Delve for Go, debugpy for Python, node inspect for Node.js,
  rust-gdb/rust-lldb for Rust, gdb/lldb for C/C++/Zig/binary).
- Produces machine-friendly JSON summary (metadata + raw logs) intended to be consumed by an AI agent.
- Safer command construction (uses shutil.which, shlex.quote, avoids shell=True where possible).
- Retains qemu-user fallback for cross-arch when available.

Usage: import Debugger and call Debugger().debug(...)

Note: This tool still executes compilers/debuggers on the host. Only run on trusted code or in an isolated environment.
"""

import subprocess
import tempfile
import os
import shlex
import shutil
import socket
import time
import json
from typing import Dict, Optional, Union, Literal, Tuple
from datetime import datetime


class Debugger:
    """
    CTF-focused debugger with multi-debugger selection and structured output.
    """

    EXT_LANG_MAP = {
        '.c': 'c',
        '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.c++': 'cpp',
        '.rs': 'rust',
        '.go': 'go',
        '.zig': 'zig',
        '.py': 'python',
        '.js': 'node',
        '.mjs': 'node',
        '.ts': 'node',
        '.rb': 'ruby',
        '.php': 'php',
        '.sh': 'bash',
        '.pl': 'perl',
        '.java': 'java',
        '.jar': 'java',
    }

    ARCH_MAP = {
        'x86-64': ('i386:x86-64', None),
        'x86_64': ('i386:x86-64', None),
        'intel 80386': ('i386', None),
        'i386': ('i386', None),
        'aarch64': ('aarch64', 'qemu-aarch64'),
        'arm64': ('aarch64', 'qemu-aarch64'),
        'arm': ('arm', 'qemu-arm'),
        'mips': ('mips', 'qemu-mips'),
    }

    # preferred debugger per language
    PREFERRED_DEBUGGER = {
        'go': 'dlv',          # Delve
        'python': 'debugpy',  # debugpy (python adapter)
        'node': 'node-inspect',
        'c': 'gdb',
        'cpp': 'gdb',
        'rust': 'rust-gdb',   # fallback to rust-gdb then rust-lldb then gdb
        'zig': 'gdb',
        'binary': 'gdb',
    }

    def __init__(self):
        pass

    # ----------------- utility helpers -----------------

    @staticmethod
    def _read_shebang(path: str) -> Optional[str]:
        try:
            with open(path, 'rb') as f:
                start = f.read(128)
            if start.startswith(b'#!'):
                try:
                    return start.split(b'\n', 1)[0].decode('utf-8', 'ignore')
                except Exception:
                    return None
            return None
        except Exception:
            return None

    @staticmethod
    def _is_binary_file(file_path: str) -> bool:
        try:
            completed = subprocess.run(['file', '--brief', '--mime-type', file_path],
                                       capture_output=True, text=True, check=True)
            mime = completed.stdout.strip()
            return not mime.startswith('text/')
        except Exception:
            TEXT_EXTENSIONS = {'.c', '.cpp', '.cc', '.py', '.java', '.txt', '.h', '.rs', '.go', '.js', '.rb', '.php', '.sh'}
            return os.path.splitext(file_path)[1].lower() not in TEXT_EXTENSIONS

    def _detect_language(self, path: str, explicit_lang: Optional[str]) -> str:
        if explicit_lang:
            return explicit_lang.lower()
        ext = os.path.splitext(path)[1].lower()
        if ext in self.EXT_LANG_MAP:
            return self.EXT_LANG_MAP[ext]
        shebang = self._read_shebang(path)
        if shebang:
            if 'python' in shebang:
                return 'python'
            if 'node' in shebang or 'nodejs' in shebang:
                return 'node'
            if 'ruby' in shebang:
                return 'ruby'
            if 'php' in shebang:
                return 'php'
            if 'bash' in shebang or 'sh' in shebang:
                return 'bash'
        if self._is_binary_file(path):
            return 'binary'
        return 'unknown'

    def _ensure_toolchain(self, lang: str):
        tool_map = {
            'c': ['gcc', 'clang'],
            'cpp': ['g++', 'clang++'],
            'rust': ['rustc', 'cargo'],
            'go': ['go', 'dlv'],
            'zig': ['zig'],
            'python': ['python3'],
            'node': ['node'],
            'ruby': ['ruby'],
            'php': ['php'],
            'bash': ['bash', 'sh'],
            'java': ['java', 'javac'],
            'binary': [],
            'unknown': []
        }
        required = tool_map.get(lang, [])
        for exe in required:
            if shutil.which(exe):
                return
        if required:
            pretty = ", ".join(required)
            raise RuntimeError(f"Required tool(s) for language '{lang}' not found: {pretty}. Install them and ensure they're on PATH.")

    def _compile_source(self, path: str, lang: str) -> str:
        base = os.path.splitext(path)[0]
        out = base + ".ctf"
        env = None

        if lang == 'c':
            cmd = ['gcc', '-g', '-O0', '-fno-stack-protector', '-no-pie', '-z', 'execstack', path, '-o', out]
        elif lang == 'cpp':
            cmd = ['g++', '-g', '-O0', '-std=c++17', '-fno-stack-protector', '-no-pie', '-z', 'execstack', path, '-o', out]
        elif lang == 'rust':
            cmd = ['rustc', '-C', 'debuginfo=2', '-C', 'opt-level=0', path, '-o', out]
        elif lang == 'go':
            host_uname = self._host_arch()
            host_to_goarch = {
                'x86_64': 'amd64', 'amd64': 'amd64',
                'aarch64': 'arm64', 'arm64': 'arm64',
                'armv7l': 'arm', 'armv7': 'arm',
                'i386': '386', 'i686': '386'
            }
            goarch = host_to_goarch.get(host_uname, None)
            try:
                goos_completed = subprocess.run(['go', 'env', 'GOOS'], capture_output=True, text=True, check=True)
                goos = goos_completed.stdout.strip() or os.uname().sysname.lower()
            except Exception:
                goos = os.uname().sysname.lower() if hasattr(os, 'uname') else 'linux'

            env = os.environ.copy()
            if goarch:
                env['GOARCH'] = goarch
                env['GOOS'] = goos
            cmd = ['go', 'build', '-gcflags', 'all=-N -l', '-o', out, path]
        elif lang == 'zig':
            cmd = ['zig', 'build-exe', path, '-g', '-O', 'DebugFast', '-fno-stack-protector', '-lc', '-o', out]
        else:
            raise RuntimeError(f"Unsupported compile language: {lang}")

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Compilation failed ({lang}): {e.stderr or e.stdout}")
        return out

    def _detect_binary_arch(self, path: str) -> Tuple[str, Optional[str]]:
        try:
            completed = subprocess.run(['file', '--brief', path], capture_output=True, text=True, check=True)
            out = completed.stdout.lower()
        except Exception:
            return "", None

        for key, (gdbarch, qemu_prog) in self.ARCH_MAP.items():
            if key in out:
                return gdbarch, qemu_prog
        if 'elf 64-bit' in out or 'mach-o 64-bit' in out:
            if 'arm' in out or 'aarch64' in out or 'arm64' in out:
                return 'aarch64', 'qemu-aarch64'
            return 'i386:x86-64', None
        if 'elf 32-bit' in out:
            return 'i386', None
        return "", None

    @staticmethod
    def _host_arch() -> str:
        try:
            uname = subprocess.run(['uname', '-m'], capture_output=True, text=True, check=True)
            return uname.stdout.strip().lower()
        except Exception:
            try:
                import platform
                return platform.machine().lower()
            except Exception:
                return ""

    @staticmethod
    def _archs_match(host_arch: str, binary_gdb_arch: str) -> bool:
        if not host_arch or not binary_gdb_arch:
            return False
        host = host_arch.lower()
        binar = binary_gdb_arch.lower()
        if host in ('x86_64', 'amd64') and 'x86-64' in binar:
            return True
        if host in ('aarch64', 'arm64') and 'aarch64' in binar:
            return True
        if host.startswith('arm') and 'arm' in binar and 'aarch64' not in binar:
            return True
        if host.startswith('mips') and 'mips' in binar:
            return True
        return False

    @staticmethod
    def _find_free_port() -> int:
        s = socket.socket()
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
        s.close()
        return port

    # ----------------- script creation helpers -----------------

    def _create_gdb_script(self, binary_for_file_cmd: str,
                           break_target: Union[int, str],
                           expressions: str,
                           mode: str = 'local',
                           remote_port: Optional[int] = None,
                           gdb_arch: Optional[str] = None) -> str:
        file_cmd_arg = shlex.quote(binary_for_file_cmd)
        exprs_list = [e.strip() for e in (expressions or "").split(',') if e.strip()]

        s = str(break_target).strip()
        break_cmd = f"break {shlex.quote(s)}" if s else ""

        lines = []
        lines.append("set pagination off")
        lines.append("set confirm off")
        if gdb_arch:
            lines.append(f"set architecture {gdb_arch}")

        # source runtime-gdb.py only if present (best-effort)
        runtime_gdb_py = '/usr/local/go/src/runtime/runtime-gdb.py'
        if os.path.exists(runtime_gdb_py):
            lines.append(f"source {runtime_gdb_py}")

        lines.append("show architecture")
        lines.append(f"file {file_cmd_arg}")

        if mode == 'local':
            if break_cmd:
                lines.append(break_cmd)
            lines.append("run")
        else:
            if break_cmd:
                lines.append(break_cmd)
            lines.append(f"target remote :{remote_port}")
            lines.append("continue")

        lines.append('printf "\\n=== DISASSEMBLY AROUND PC ===\\n"')
        lines.append("x/32i $pc-8")
        lines.append('printf "\\n=== REGISTERS ===\\n"')
        lines.append("info registers")
        lines.append('printf "\\n=== STACK TOP ===\\n"')
        lines.append("x/64wx $sp")
        lines.append('printf "\\n=== SYMBOLS (some) ===\\n"')
        lines.append("info functions")

        for expr in exprs_list:
            safe = expr
            lines.append(f'printf "\\n=== EXPR: {safe} ===\\n"')
            if safe.startswith("0x"):
                lines.append(f"x/64xb {safe}")
                lines.append(f'x/s {safe}')
            else:
                lines.append(f'print/x (void*)&{safe}')
                lines.append(f'print/x {safe}')
                lines.append(f'x/64xb &{safe}')
                lines.append(f'x/s &{safe}')

        lines.append('printf "\\n=== SEARCH COMMON STRINGS NEAR PC ===\\n"')
        lines.append('find $pc, $pc + 8192, "/bin/sh"')
        lines.append('find $pc, $pc + 8192, "flag"')
        lines.append('find $pc, $pc + 8192, "system"')
        lines.append("quit")

        script = "\n".join(lines)
        fd, path = tempfile.mkstemp(suffix='.gdb')
        with os.fdopen(fd, 'w') as f:
            f.write(script)
        return path

    # ----------------- main debug entry -----------------

    def debug(self, file: str, line: Union[int, str] = "", exprs: str = "",
              input_vars: Optional[Dict[str, Union[str, int, float]]] = None,
              lang: Optional[str] = None,
              timeout_seconds: int = 180) -> Tuple[str, str]:
        if not os.path.exists(file):
            raise FileNotFoundError(file)

        detected = self._detect_language(file, lang)
        self._ensure_toolchain(detected)

        # Interpreted languages: spawn language-appropriate debug servers instead
        if detected in ('python', 'node', 'ruby', 'php', 'bash', 'perl', 'java'):
            return self._debug_interpreted(file, detected, line, exprs, input_vars, timeout_seconds)

        compiled_by_us = False
        run_binary_path = None

        if detected in ('c', 'cpp', 'rust', 'go', 'zig'):
            run_binary_path = self._compile_source(file, detected)
            compiled_by_us = True
        elif detected == 'binary':
            run_binary_path = file
        else:
            raise RuntimeError(f"Unsupported or unknown file type ({detected}).")

        gdb_arch, qemu_prog = self._detect_binary_arch(run_binary_path)
        host = self._host_arch()
        arch_ok = self._archs_match(host, gdb_arch)

        use_qemu = False
        qemu_proc = None
        dbg_proc = None
        script_path = None

        # Decide which native debugger to run
        try:
            # Prefer lldb on Darwin if available for native compiled languages
            host_is_darwin = (os.uname().sysname.lower() == 'darwin') if hasattr(os, 'uname') else False

            debugger_cmd = None
            debugger_name = None

            if detected == 'go':
                # Delve is best for Go
                dlv = shutil.which('dlv')
                if not dlv:
                    raise RuntimeError('Delve (dlv) not found in PATH. Install github.com/go-delve/delve/cmd/dlv')
                port = self._find_free_port()
                # headless so we can capture logs, use a short-lived listen on random port
                debugger_cmd = [dlv, 'exec', run_binary_path, f'--listen=127.0.0.1:{port}', '--api-version=2', '--accept-multiclient', '--allow-non-terminal-interactive=true', '--log']
                debugger_name = 'dlv'
            else:
                # For rust prefer rust-gdb or rust-lldb
                if detected == 'rust':
                    candidates = ['rust-gdb', 'rust-lldb', 'gdb', 'lldb']
                else:
                    # c/cpp/zig/binary
                    if host_is_darwin and shutil.which('lldb'):
                        candidates = ['lldb', 'gdb', 'gdb-multiarch']
                    else:
                        candidates = ['gdb-multiarch', 'gdb', 'lldb']

                found = None
                for c in candidates:
                    pathc = shutil.which(c)
                    if pathc:
                        found = pathc
                        debugger_name = c
                        break
                if not found:
                    raise RuntimeError('No suitable debugger found on PATH (gdb/gdb-multiarch/lldb/rust-gdb).')

                # If we need qemu because arch mismatch, launch qemu-user and connect remotely
                if not arch_ok:
                    if not qemu_prog or shutil.which(qemu_prog) is None:
                        raise RuntimeError(f"Binary architecture '{gdb_arch}' does not match host '{host}', and qemu-user ('{qemu_prog}') not found.")
                    port = self._find_free_port()
                    qemu_cmd = [qemu_prog, '-g', str(port), run_binary_path]
                    qemu_proc = subprocess.Popen(qemu_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    time.sleep(0.3)
                    # create gdb script that does 'target remote :port'
                    script_path = self._create_gdb_script(run_binary_path, line, exprs, mode='remote', remote_port=port, gdb_arch=gdb_arch)
                    # Use the found debugger in remote mode
                    debugger_cmd = [found, '-q', '-x', script_path]
                else:
                    # native run
                    if debugger_name and debugger_name.startswith('lldb'):
                        # LLDB: create a short lldb command script file
                        lldb_cmds = []
                        if line:
                            lldb_cmds.append(f'breakpoint set -n {shlex.quote(str(line))}')
                        lldb_cmds.append(f'target create {shlex.quote(run_binary_path)}')
                        lldb_cmds.append('run')
                        lldb_cmds.append('thread backtrace all')
                        lldb_cmds.append('quit')
                        fd, script_path = tempfile.mkstemp(suffix='.lldb')
                        with os.fdopen(fd, 'w') as f:
                            f.write('\n'.join(lldb_cmds))
                        debugger_cmd = ['lldb', '-s', script_path]
                    else:
                        # GDB path: create gdb script and run with -x
                        script_path = self._create_gdb_script(run_binary_path, line, exprs, mode='local', gdb_arch=gdb_arch)
                        debugger_cmd = [found, '-q', '-x', script_path, '--args', run_binary_path]

            # Print script for debugging visibility (and AI agent consumption)
            if script_path and os.path.exists(script_path):
                try:
                    with open(script_path, 'r') as f:
                        script_contents = f.read()
                except Exception:
                    script_contents = ''
            else:
                script_contents = ''
            
            print(f"Debugger command: {debugger_cmd}")
            # Launch debugger process
            dbg_proc = subprocess.Popen(
                debugger_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            commands = """
            break main.main
            call
            next
            exit
            """

            stdout, stderr = dbg_proc.communicate(commands)
            stdout, stderr = dbg_proc.communicate(timeout=timeout_seconds)

            # collect qemu stderr if present
            if qemu_proc:
                try:
                    q_stdout, q_stderr = qemu_proc.communicate(timeout=0.2)
                except Exception:
                    q_stdout, q_stderr = "", ""
                if q_stderr:
                    stderr = (stderr or "") + "\n--- qemu stderr ---\n" + q_stderr

            # produce structured JSON summary for AI agent
            summary = {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'language': detected,
                'debugger': debugger_name,
                'debugger_cmd': debugger_cmd,
                'script': script_contents,
                'binary': run_binary_path,
                'arch_detected': gdb_arch,
                'host_arch': host,
                'arch_ok': arch_ok,
                'stdout': stdout,
                'stderr': stderr,
                'success': True
            }

            json_summary = json.dumps(summary)

            # Return human-readable stdout/stderr, but also print JSON on stderr for machine consumption
            # (so agent can parse the last line). We also return (stdout, stderr_with_json) tuple.
            stderr_with_json = (stderr or '') + '\n\n__DEBUG_SUMMARY_JSON_START__\n' + json_summary + '\n__DEBUG_SUMMARY_JSON_END__\n'

            # Also print to console for users
            print('--- DEBUGGER STDOUT ---')
            print(stdout)
            print('--- DEBUGGER STDERR ---')
            print(stderr)
            print('--- DEBUGGER JSON SUMMARY ---')
            print(json_summary)

            return stdout, stderr_with_json

        finally:
            # cleanup
            try:
                if script_path and os.path.exists(script_path):
                    os.remove(script_path)
            except Exception:
                pass
            if compiled_by_us and run_binary_path and os.path.exists(run_binary_path):
                try:
                    os.remove(run_binary_path)
                except Exception:
                    pass
            try:
                if dbg_proc and dbg_proc.poll() is None:
                    dbg_proc.kill()
            except Exception:
                pass
            try:
                if qemu_proc and qemu_proc.poll() is None:
                    qemu_proc.kill()
            except Exception:
                pass

    # ----------------- interpreted debug helpers -----------------

    def _debug_interpreted(self, file: str, detected: str, line: Union[int, str], exprs: str, input_vars: Optional[Dict], timeout_seconds: int):
        """
        Launch language-specific debug adapter or inspector for interpreted languages and capture logs.
        Returns (stdout, stderr_with_json)
        """
        if detected == 'python':
            # Use debugpy: start python with debugpy adapter listening on a free port
            debugpy = shutil.which('python3') or shutil.which('python')
            if not debugpy:
                raise RuntimeError('Python not found')
            port = self._find_free_port()
            cmd = [debugpy, '-m', 'debugpy', '--listen', f'127.0.0.1:{port}', '--wait-for-client', file]
            tool = 'debugpy'
        elif detected == 'node':
            node = shutil.which('node')
            if not node:
                raise RuntimeError('node not found')
            port = self._find_free_port()
            cmd = [node, f'--inspect-brk={port}', file]
            tool = 'node-inspect'
        elif detected == 'java':
            # Start the JVM with JDWP agent (requires building .class/.jar first). Here we attempt to run jar.
            java = shutil.which('java')
            if not java:
                raise RuntimeError('java not found')
            port = self._find_free_port()
            # Note: user must provide a runnable jar for this branch
            cmd = [java, f'-agentlib:jdwp=transport=dt_socket,server=y,suspend=y,address={port}', '-jar', file]
            tool = 'jdb'
        else:
            raise RuntimeError(f'Interpreted debug for {detected} not implemented in this helper')

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            stdout, stderr = proc.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()

        summary = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'language': detected,
            'debugger': tool,
            'cmd': cmd,
            'stdout': stdout,
            'stderr': stderr,
            'success': proc.returncode == 0
        }
        json_summary = json.dumps(summary)
        stderr_with_json = (stderr or '') + '\n\n__DEBUG_SUMMARY_JSON_START__\n' + json_summary + '\n__DEBUG_SUMMARY_JSON_END__\n'

        print('--- INTERPRETED DEBUG STDOUT ---')
        print(stdout)
        print('--- INTERPRETED DEBUG STDERR ---')
        print(stderr)
        print('--- INTERPRETED DEBUG JSON SUMMARY ---')
        print(json_summary)

        return stdout, stderr_with_json


if __name__ == "__main__":
    dbg = Debugger()
    # Example: debug the Go file (replace with your path)
    try:
        out, err = dbg.debug("code/vulnerable.go", "main.main", "filename, result")
        print('\n=== STDOUT ===')
        print(out)
        print('\n=== STDERR (with JSON) ===')
        print(err)
    except Exception as e:
        print(json.dumps({'error': str(e)}))
