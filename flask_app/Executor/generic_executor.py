import json
import subprocess
import platform
import logging
import re
from abc import ABC, abstractmethod
import shlex
import os
import shutil
import tempfile
from pathlib import Path
import os, re, json, shutil, tempfile, logging, subprocess
from pathlib import Path

class Generic_Executor(ABC):

    @abstractmethod
    def initiate_sub_execution_protocol(sub_ep):
        from Executor.orchestrator import Orchestrator
        sub_exec = Orchestrator(sub_ep)
        result=sub_exec.start_execution(is_sub_ep=True)
        return result

    @abstractmethod
    def set_execution_sequence(parameter_type, parameter_array, execution_requests):
        pass
    
    @staticmethod
    def needs_shell(s: str) -> bool:

        # If a command string contains any of these, it is run via shell
        _SHELL_CHARS = set("&|;><*(){}~`$")
        return any(ch in s for ch in _SHELL_CHARS)

    def split_items(*items):
        """Yield tokens from items, splitting on commas first, then shell-aware split."""
        for item in items:
            if not item:
                continue
            # If it's a single string that looks like a whole command line, return as-is
            if isinstance(item, str) and Generic_Executor.needs_shell(item):
                # mark as 'shell' by returning a tuple
                yield ("__SHELL__", item.strip())
                continue
            # Otherwise, split by comma, then shlex
            parts = [p.strip() for p in str(item).split(",") if p and p.strip()]
            for p in parts:
                for tok in shlex.split(p):
                    if tok: yield tok

    def normalize_apt_pkgs(pkgs, PKG_MAP_APT):
        out = []
        for p in pkgs:
            if p.lower() == "sudo":
                continue
            out.extend(PKG_MAP_APT.get(p, [p]))
        return out

    def run_cmd(cmd, *, shell=False):
        ENV = dict(os.environ, DEBIAN_FRONTEND="noninteractive")
        if shell:
            print("Command (shell):", cmd)
            subprocess.run(["bash", "-lc", cmd], check=True, env=ENV)
        else:
            print("Command:", cmd)
            subprocess.run(cmd, check=True, env=ENV)

    def manage_installation_requirements(installations):
        if installations is None:
            return 
        system = platform.system()
        try:
            if system == 'Linux':
                # minimal mapping for Debian/Ubuntu
                PKG_MAP_APT = {
                    "python": ["python3", "python-is-python3"],   # old -> new + shim
                    "pip": ["python3-pip"],
                    "python-pip": ["python3-pip"],
                }
                # For Debian/Ubuntu systems:
                apt_updated = False

                for sublist in installations:
                    if not sublist:
                        continue

                    head = (sublist[0] or "").strip().lower()

                    # --- 1) <OS command> → apt-get install ---
                    if head == "<os command>":
                        tokens = list(Generic_Executor.split_items(*sublist[1:]))
                        # If any item was a full shell command, run it as-is first (rare but allowed)
                        for i, t in enumerate(tokens):
                            if isinstance(t, tuple) and t[0] == "__SHELL__":
                                # Run arbitrary shell command before apt install tokens
                                Generic_Executor.run_cmd(t[1], shell=True)
                                tokens[i] = None
                        tokens = [t for t in tokens if isinstance(t, str)]

                        apt_pkgs = Generic_Executor.normalize_apt_pkgs(tokens, PKG_MAP_APT)
                        if apt_pkgs:
                            if not apt_updated:
                                Generic_Executor.run_cmd(["apt-get", "update"])
                                apt_updated = True
                            Generic_Executor.run_cmd(["apt-get", "install", "-y", "--no-install-recommends", *apt_pkgs])

                    # --- 2) pip install ... ---
                    elif head.startswith("pip install") or head == "pip" or head == "pip3" or head.startswith("pip3 install"):
                        # Collect pip packages from the rest of the sublist
                        tokens = []
                        # If head contains packages too (e.g. "pip install numpy pillow"), include them
                        head_tail = head.split(None, 2)  # ["pip","install","rest..."]
                        if len(head_tail) == 3:
                            tokens.extend(shlex.split(head_tail[2]))

                        tokens.extend(list(Generic_Executor.split_items(*sublist[1:])))

                        # Optional mapping: if someone wrote "python" here, ignore mapping (pip has no such package),
                        # but if you *do* want to map pip tokens, adjust here. We'll only drop stray 'sudo'.
                        pip_pkgs = [t for t in tokens if isinstance(t, str) and t.lower() != "sudo"]

                        if pip_pkgs:
                            Generic_Executor.run_cmd(["python3", "-m", "pip", "install", "--no-cache-dir", *pip_pkgs])

                    # --- 3) Arbitrary command: execute as-is ---
                    else:
                        # If the sublist looks like a single shell command string with operators, run via shell.
                        # Otherwise treat it as argv tokens.
                        flat = list(Generic_Executor.split_items(*sublist))
                        # If there is exactly one "__SHELL__" entry and nothing else, run that
                        only_shell = [t for t in flat if isinstance(t, tuple) and t[0] == "__SHELL__"]
                        non_shell = [t for t in flat if isinstance(t, str)]

                        if only_shell and not non_shell:
                            Generic_Executor.run_cmd(only_shell[0][1], shell=True)
                        else:
                            # Clean out 'sudo' since in containers it's usually not present/needed
                            argv = [t for t in non_shell if t.lower() != "sudo"]
                            if not argv:
                                continue
                            # If the first token is "apt-get" and it's an install, ensure we updated once
                            if argv[:2] == ["apt-get", "install"] and not apt_updated:
                                Generic_Executor.run_cmd(["apt-get", "update"])
                                apt_updated = True
                            Generic_Executor.run_cmd(argv)
            
            elif system == 'Darwin':  # macOS
                # Installing Python via Homebrew:
                commands = []

                for sublist in installations:
                    cmd = []
                    for item in sublist:
                        if item is None:
                            continue
                        if item == "<OS command>":
                            cmd.extend(['brew', 'install'])
                        else:
                            parts = [part.strip() for part in item.split(',')]
                            for part in parts:
                                cmd.extend(part.split())  # Split by spaces as well
                    if cmd:
                        commands.append(cmd)

                # Print and optionally run
                for cmd in commands:
                    print("Command:", cmd)
                    subprocess.run(cmd, check=True)
                return
            elif system == 'Windows':
                # For Windows, assume Chocolatey is installed:
                cmd=['choco', 'install',]
                cmd.extend(installations)
                subprocess.run(cmd, check=True)
                return
            else:
                logging.error("Unsupported operating system for installation requirements")
        except subprocess.CalledProcessError as e:
            logging.error(f"Error installing: {e}")
    
    def extend_execution_sequence_single_request(parameter, execution_requests, arg_separator=""):
        if isinstance(parameter[1], dict):
            temp_execution_requests = {}
            index=1
            sub_eps=Generic_Executor.initiate_sub_execution_protocol(parameter[1])
            if len(execution_requests)>1:
                for request in execution_requests:
                    for sub_ep in sub_eps.values():
                        temp_execution_requests[index]=execution_requests[request]+parameter[0]+" "+sub_ep+arg_separator
                        index+=1
                    index+=1
            elif len(execution_requests)==1:
                for sub_ep in sub_eps.values():
                    temp_execution_requests[index]=execution_requests[1]+parameter[0]+" "+sub_ep+arg_separator
                    index+=1
            else:
                for sub_ep in sub_eps.values():
                    temp_execution_requests[index]=parameter[0]+" "+sub_ep+arg_separator
                    index+=1
            execution_requests=temp_execution_requests

        elif isinstance(parameter[1], list):
            if len(execution_requests)>1:
                for request in execution_requests:
                    execution_requests[request]+=parameter[0]+" "+arg_separator
                    for value in parameter[1]:
                        execution_requests[request]+=value+","
                    execution_requests[request]+=arg_separator
            else:
                execution_requests[1]+=parameter[0]+" "
                for value in parameter[1]:
                    execution_requests[1]+=value+","
                execution_requests[1]+=arg_separator
        else:
            if len(execution_requests)>1:
                for request in execution_requests:
                    execution_requests[request]+=parameter[0]+" "+parameter[1]+arg_separator
            elif len(execution_requests)==1:
                execution_requests[1]+=parameter[0]+" "+parameter[1]+arg_separator
            else:
                execution_requests[1]=parameter[0]+" "+parameter[1]+arg_separator
        return execution_requests
    
    def extend_execution_sequence_multiple_request(parameter, execution_requests, arg_separator=""):
        if isinstance(parameter[1], dict):
            temp_execution_requests = {}
            index=1
            sub_eps=Generic_Executor.initiate_sub_execution_protocol(parameter[1])
            if len(execution_requests)>1:
                for request in execution_requests:
                    for sub_ep in sub_eps.values():
                        temp_execution_requests[index]=execution_requests[request]+parameter[0]+" "+sub_ep+arg_separator
                        index+=1
                    index+=1
            elif len(execution_requests)==1:
                for sub_ep in sub_eps.values():
                    temp_execution_requests[index]=execution_requests[1]+parameter[0]+" "+sub_ep+arg_separator
                    index+=1
            else:
                for sub_ep in sub_eps.values():
                    temp_execution_requests[index]=parameter[0]+" "+sub_ep+arg_separator
                    index+=1
            execution_requests=temp_execution_requests
        elif isinstance(parameter[1], list):
            temp_execution_requests = {}
            index=1
            if len(execution_requests)>1:
                for request in execution_requests:
                    for value in parameter[1]:
                        temp_execution_requests[index]=execution_requests[request]+parameter[0]+" "+value+arg_separator
                        index+=1
                    index+=1
            elif len(execution_requests)==1:
                for value in parameter[1]:
                    temp_execution_requests[index]=execution_requests[1]+parameter[0]+" "+value+arg_separator
                    index+=1
            else:
                for value in parameter[1]:
                   temp_execution_requests[index]=parameter[0]+" "+value+arg_separator
                index+=1
            execution_requests=temp_execution_requests
        else:
            if len(execution_requests)>1:
                for request in execution_requests:
                    execution_requests[request]+=parameter[0]+" "+parameter[1]+arg_separator
            elif len(execution_requests)==1:
                execution_requests[1]+=parameter[0]+" "+parameter[1]+arg_separator
            else:
                execution_requests[1]=parameter[0]+" "+parameter[1]+arg_separator

        return execution_requests
    
    @staticmethod
    @abstractmethod
    def stage_ep():
        pass

    @staticmethod
    @abstractmethod
    def check_parameter():
        pass

    def execute_requests(execution_requests):
        resolved_results = {}
        for k, v in execution_requests.items():
            if isinstance(v, str):
                logging.warning(f"\nProcessing entry {k}...")
                resolved_results[k] = Generic_Executor.execute_command(v)

        return resolved_results
    
    def replace_sub_execution(text):
    # The regex finds "sub_execution:" followed by a { then any number of non-"}" characters, until the first "}".
    # This assumes that the dictionary does not contain nested } characters.
        return re.sub(r'sub_execution:\{[^}]+\}', '-', text)
    
    # -------- helpers -----------------------------------------------------------

    @staticmethod
    def _snapshot(dirpath: Path):
        """Return set of relative file paths under dirpath."""
        return {p.relative_to(dirpath) for p in dirpath.rglob("*") if p.is_file()}

    @staticmethod
    def _has_files(p: Path) -> bool:
        return p.exists() and any(x.is_file() for x in p.rglob("*"))

    @staticmethod
    def _localize_common_inputs(command_str: str, work_dir: Path) -> str:
        """
        Best-effort: copy obvious input paths into sandbox and rewrite command so
        scripts that derive output dirs from input locations write inside sandbox.
        Handles:
        --file=PATH, --file PATH, -f PATH
        bare PATH tokens (that exist)
        Falls back to the original command if parsing fails.
        """
        try:
            parts = shlex.split(command_str)
        except ValueError:
            return command_str

        new_parts = []
        i = 0
        while i < len(parts):
            tok = parts[i]

            # --key=value (we only special-case --file=VALUE and -f=VALUE)
            if tok.startswith("--file=") or tok.startswith("-f="):
                path = Path(tok.split("=", 1)[1].strip("'\""))
                if path.exists():
                    dst = work_dir / path.name
                    shutil.copy2(path, dst) if path.is_file() else shutil.copytree(path, dst, dirs_exist_ok=True)
                    tok = tok.split("=", 1)[0] + "=" + str(dst)
                new_parts.append(tok)

            # --file VALUE  |  -f VALUE
            elif tok in ("--file", "-f") and i + 1 < len(parts):
                val = parts[i + 1]
                path = Path(val.strip("'\""))
                if path.exists():
                    dst = work_dir / path.name
                    shutil.copy2(path, dst) if path.is_file() else shutil.copytree(path, dst, dirs_exist_ok=True)
                    new_parts.extend([tok, str(dst)])
                    i += 2
                    continue
                new_parts.extend([tok, val])
                i += 2
                continue

            else:
                # bare path token (that exists) and not a flag
                if not tok.startswith("-"):
                    path = Path(tok.strip("'\""))
                    if path.exists():
                        dst = work_dir / path.name
                        shutil.copy2(path, dst) if path.is_file() else shutil.copytree(path, dst, dirs_exist_ok=True)
                        tok = str(dst)
                new_parts.append(tok)

            i += 1

        return shlex.join(new_parts)

    # -------- main --------------------------------------------------------------

    @staticmethod
    def execute_command(command_str: str):
        """
        Run a command in an isolated temp dir. Always return a ZIP:
        - If files are created, zip those (prefer known output dirs).
        - Else, write stdout (pretty JSON if possible) / stderr to files and zip them.
        - Plus: try to localize inputs and harvest absolute paths printed by the script.
        """
        work_dir = Path(tempfile.mkdtemp(prefix="job_"))
        logging.warning(f"Executing in isolated workspace: {work_dir}")

        # Nudge temp usage into sandbox (many libs respect TMPDIR)
        env = os.environ.copy()
        env["TMPDIR"] = env.get("TMPDIR", str(work_dir))

        # Best-effort localization so outputs land inside the sandbox
        cmd = Generic_Executor._localize_common_inputs(command_str, work_dir)
        logging.warning(f"Command (localized if possible): {cmd}")

        # Snapshot before
        before = Generic_Executor._snapshot(work_dir)

        # Run
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=work_dir,
            capture_output=True,
            text=True,
            env=env,
        )

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        logging.warning(f"Command stdout:\n{stdout[:1000] + ('...' if len(stdout) > 1000 else '')}")
        logging.warning(f"Command stderr:\n{stderr[:1000] + ('...' if len(stderr) > 1000 else '')}")

        # Snapshot after
        after = Generic_Executor._snapshot(work_dir)
        created = sorted(after - before)

        # 1) Prefer common output dirs if they exist (same as your old function)
        preferred = None
        for dname in ("png_images", "output"):
            d = work_dir / dname
            if Generic_Executor._has_files(d):
                preferred = d
                break

        # 2) If nothing obvious, but files were created, collect only the new ones
        if preferred is None and created:
            collect = work_dir / "__collected__"
            collect.mkdir(parents=True, exist_ok=True)
            for rel in created:
                src = work_dir / rel
                dst = collect / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            preferred = collect

        # 3) Still nothing? Try harvesting absolute paths mentioned in stdout
        if preferred is None and stdout:
            harvest = work_dir / "__harvested__"
            found = 0
            # Look for absolute paths with common artifact extensions
            exts = r"(png|jpe?g|tiff?|gif|bmp|pdf|csv|json|parquet|txt|zip|npy)"
            for path_str in set(re.findall(rf"(/[^ \t\n\r\"']+\.(?:{exts}))", stdout, flags=re.I)):
                p = Path(path_str)
                if p.exists() and p.is_file():
                    harvest.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p, harvest / p.name)
                    found += 1
            if found > 0:
                preferred = harvest

        # 4) If still nothing, persist stdout/stderr so we can zip them (JSON pretty if possible)
        if preferred is None:
            preferred = work_dir / "output"
            preferred.mkdir(parents=True, exist_ok=True)

            # Try to store stdout as pretty JSON; else plain text
            if stdout:
                try:
                    parsed = json.loads(stdout)
                    (preferred / "response.json").write_text(json.dumps(parsed, indent=2))
                except Exception:
                    (preferred / "stdout.txt").write_text(stdout)

            if stderr:
                (preferred / "stderr.txt").write_text(stderr)

        # 5) Create the ZIP next to (but not inside) the folder we zip
        zip_path = work_dir / "artifacts.zip"
        shutil.make_archive(str(zip_path.with_suffix("")), "zip", root_dir=preferred)

        return {
            "stdout": stdout,
            "stderr": stderr,
            "returncode": result.returncode,
            "zip_path": str(zip_path),
            "work_dir": str(work_dir),
        }