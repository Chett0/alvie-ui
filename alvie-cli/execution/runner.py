from datetime import datetime
from io import TextIOWrapper
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

from config.loaders import load_output_symbols
from tui.flow import ConfigArg, is_debug_enabled
from client.viewer import Viewer

from terminal.style import (
    DEBUG_PARSED_OUTPUT_ERROR,
    info,
    warn,
    error,
    success,
    hint,
    style,
    CYAN,
    BOLD,
    style
)

from terminal.widgets import Spinner

from models.parsed_output import (
    SymbolParser, 
    ParsedOutput, 
    ParsedHypothesis
)

@dataclass
class AlvieExecution:
    """A single ALVIE execution with its arguments and output settings."""

    alvie_path: Path
    executable: str
    args: list[ConfigArg] = field(default_factory=list)
    is_raw_output: bool = field(default=False)
    output_path: Path | None = field(default=None)
    parsed_output_path: Path | None = field(default=None)
    parallel: bool = field(default=False)
    interactive: bool = field(default=False)
    upload_name: str | None = field(default=None)

    parsed_document: dict | None = field(default=None, init=False, repr=False)

    _process: subprocess.Popen | None = field(default=None, init=False, repr=False)
    _spinner: Spinner | None = field(default=None, init=False, repr=False)
    _output_file: TextIOWrapper | None = field(default=None, init=False, repr=False)

    _start_time : datetime | None = field(default=None, init=False, repr=False)
    _end_time : datetime | None = field(default=None, init=False, repr=False)

    @property
    def exe(self) -> str:
        """Path to the ALVIE executable to invoke."""
        return f"bin/{self.executable}"

    @property
    def args_string(self) -> list[str]:
        """Arguments flattened into CLI tokens (``["--flag", "value", ...]``)."""
        tokens: list[str] = []
        for arg in self.args:
            tokens.append(arg.flag)
            if arg.value is not None:
                tokens.append(arg.value)
        return tokens

    @property
    def command(self) -> list[str]:
        """Full command line passed to the subprocess."""
        return ["dune", "exec", "--display=quiet", self.exe, "--", *self.args_string]


    def run(self) -> None:
        """Run the ALVIE execution with the specified output mode"""
        try:
            if is_debug_enabled(self.args) and self.parsed_output_path is not None:
                raise ValueError(DEBUG_PARSED_OUTPUT_ERROR)

            self._open_output_file()
            self._start_time = datetime.now()
            self._write_header()    

            if self.is_raw_output:
                self._run_raw()
            else:
                self._run_parsed()

            if self.interactive:
                self._upload_parsed_output()

        except KeyboardInterrupt:
            self._stop_spinner()
            self._terminate(force=True)  # ctrl+c sends SIGKILL to the process
            print()
            warn("Execution interrupted by user.\n")

        except subprocess.CalledProcessError as exc:
            self._stop_spinner()
            error(f"Alvie exited with a non-zero status ({exc.returncode}).\n")

        finally:
            self._close_output_file()


    def run_seq(self) -> None:
        """Run ALVIE execution with sequential output to the terminal"""
        self._print_header()
        self._process = None

        self._spinner = Spinner("Executing ALVIE").start()
        self.run()
        success("Alvie finished successfully.\n")


    def _run_raw(self) -> None:
        """Run the ALVIE execution and stream its raw output to the terminal or file."""
        try:
            self._process, stdout = self._get_alvie_process()
            received_output = False
            for line in stdout:
                if not received_output:
                    self._stop_spinner()
                    received_output = True
                self._write(line, end="", flush=True)

            self._write("\n\n")
            self._process.wait()
            self._end_time = datetime.now()

            if self._process.returncode != 0:
                raise subprocess.CalledProcessError(self._process.returncode, self.exe)
        finally:
            self._stop_spinner()


    def _run_parsed(self) -> None:
        """Run the ALVIE execution and parse its output."""
        self._process, stdout = self._get_alvie_process()

        symbols = load_output_symbols()
        input_symbols, output_symbols = symbols["inputs"], symbols["outputs"]
        parser = SymbolParser(
            input_symbols=input_symbols,
            output_symbols=output_symbols
        )

        output = ParsedOutput()

        for i, line in enumerate(stdout):
            if line.strip():
                self._stop_spinner()
                hypothesis = ParsedHypothesis.parse(
                    raw=line.strip(),
                    parser=parser,
                    output=output
                )
                output.parsed_hypotheses.append(hypothesis)
                # non-raw output is written only if an output file is specified, otherwise only the recap is printed to the terminal
                if self._output_file:
                    formatted_hypothesis = hypothesis.format()
                    self._write(f"Hypothesis {i+1}\n", formatted_hypothesis, flush=True)
                if not self.parallel:
                    self._spinner = Spinner(f"Waiting for the next hypothesis {i+2}").start()

        self._stop_spinner()
        self._process.wait()
        self._end_time = datetime.now()

        if self._process.returncode != 0:
            raise subprocess.CalledProcessError(self._process.returncode, self.exe)

        output.hypotheses_count = len(output.parsed_hypotheses)
        if not self.parallel:
            self._write(output.format_recap(parser=parser), flush=True)

        self._build_output_json(output=output)
        self._save_parsed_output()


    def _print_header(self) -> None:
        print()
        info(f"Running {style(self.executable, CYAN, BOLD)}")
        hint(f"  dune exec {self.exe} --\n")
        if self.args:
            info("Arguments:")
            for arg in self.args:
                if arg.value:
                    print(f"  {style(arg.flag, CYAN)}: {arg.value}")
                else:
                    print(f"  {style(arg.flag, CYAN)}")
        else:
            hint("  (no arguments)")
        hint("\nPress Ctrl+C to stop the execution.")
        print()


    def _write_header(self) -> None:
        """Write a header with execution information to the output file."""
        if not self._output_file:
            return

        started = (
            self._start_time.isoformat(sep=" ", timespec="seconds")
            if self._start_time else "unknown"
        )

        lines = [
            "=" * 60,
            "Start of ALVIE execution",
            f"Executable : {self.executable}",
            f"Path       : {self.exe}",
            f"Output mode       : {'raw' if self.is_raw_output else 'parsed'}",
            f"Started    : {started}",
            "Arguments  :",
        ]
        if self.args:
            for arg in self.args:
                if arg.value is not None:
                    lines.append(f"  {arg.flag}: {arg.value}")
                else:
                    lines.append(f"  {arg.flag}")
        else:
            lines.append("  (no arguments)")
        lines.append("=" * 60)

        self._write("\n".join(lines) + "\n")


    def _write_footer(self) -> None:
        """Write a footer with execution timing to the output file."""
        if not self._output_file:
            return

        ended = (
            self._end_time.isoformat(sep=" ", timespec="seconds")
            if self._end_time else "unknown"
        )

        lines = [
            "=" * 60,
            "End of ALVIE execution",
            f"Finished   : {ended}",
        ]
        if self._start_time and self._end_time:
            lines.append(f"Duration   : {self._end_time - self._start_time}")
        lines.append("=" * 60)

        self._write("\n" + "\n".join(lines) + "\n")


    def _write(
            self, 
            text: str = "", 
            end: str = "\n", 
            flush: bool = False,
        ) -> None:
        """Write produced output to the output file when set, otherwise to the terminal."""

        if self._output_file:
            self._output_file.write(f"{text}{end}")
        else:
            print(text, end=end, flush=flush)


    def _save_parsed_output(self) -> None:
        """Save parsed output as JSON when an output path is provided."""
        if not self.parsed_output_path:
            return
        try:
            self.parsed_output_path.parent.mkdir(parents=True, exist_ok=True)
            with self.parsed_output_path.open("w", encoding="utf-8") as file:
                json.dump(self.parsed_document, file, ensure_ascii=False, indent=2)
            if not self.parallel:
                print()
                info(f"Parsed output saved to {style(str(self.parsed_output_path), CYAN, BOLD)}\n")
        except OSError as exc:
            warn(f"Could not save parsed output JSON: {exc}\n")


    def _open_output_file(self) -> None:
        """Open the output file for writing when an output path is provided."""
        self._output_file = None
        if not self.output_path:
            return
        try:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            self._output_file = self.output_path.open("w", encoding="utf-8")
        except OSError as exc:
            warn(f"Could not open output file, writing to terminal instead: {exc}\n")
            self._output_file = None


    def _close_output_file(self) -> None:
        """Close the output file"""
        if not self._output_file:
            return
        self._write_footer()
        self._output_file.close()
        self._output_file = None
        if not self.parallel:
            info(f"Output saved to {style(str(self.output_path), CYAN, BOLD)}\n")


    def _build_output_json(
        self,
        output: ParsedOutput,
    ) -> None:
        """Build the JSON-serializable parsed output document."""
        self.parsed_document = {
            "executable": self.executable,
            "args": [
                {"flag": arg.flag, "value": arg.value}
                if arg.value is not None
                else {"flag": arg.flag}
                for arg in self.args
            ],
            "start": self._start_time.isoformat() if self._start_time else None,
            "end": self._end_time.isoformat() if self._end_time else None,
            "recap": {
                symbol: count
                for symbol, count in output.output_counts.items()
                if count > 0
            } | {
                "hypotheses": output.hypotheses_count,
                "runs": output.runs_count,
                "steps": output.steps_count
            },
            "hypotheses": [hypothesis.to_dict() for hypothesis in output.parsed_hypotheses],
        }
    

    def _upload_filename(self) -> str:
        """Choose a filename to store the uploaded parsed output under."""
        if self.upload_name:
            name = self.upload_name
            return name if name.endswith(".json") else f"{name}.json"
        if self.parsed_output_path:
            return self.parsed_output_path.name

        start_time = self._start_time or datetime.now()
        return f"{self.executable}-{start_time.isoformat().replace(':', '-')}.json"
    
    
    def _upload_parsed_output(self) -> None:
        """Upload execution's parsed output to the viewer backend."""
        if not self.parsed_document:
            warn(f"No parsed output to upload for {self.executable}.")
        else:
            filename = self._upload_filename()
            if not self.parallel:
                self._spinner = Spinner(f"Uploading parsed output {filename} to the Alvie viewer backend").start()
            try:
                output_id = Viewer().post_parsed_output(
                    document=self.parsed_document,
                    filename=filename,
                )
                self._stop_spinner()
                success(f"Saved parsed output for {self.executable} as {filename}.")
                info(f"\tOpen in the viewer: {Viewer().get_link(output_id)}")
            except RuntimeError as exc:
                self._stop_spinner()
                error(f"{exc}\n")
        
        print()


    def _get_alvie_process(self) -> tuple[subprocess.Popen, IO[str]]:
        """Return the ALVIE process and its stdout stream"""
        process = subprocess.Popen(
            self.command,
            cwd=self.alvie_path,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True
        )

        if not process:
            raise RuntimeError("Alvie process could not be started.")
        
        if not process.stdout:
            raise RuntimeError("No output from Alvie process.")
        
        return process, process.stdout


    def _stop_spinner(self) -> None:
        if self._spinner:
            self._spinner.stop()
            self._spinner = None


    def _terminate(self, force: bool = False) -> None:
        """Stop the running Alvie process, escalating to a kill if it does not exit."""
        process = self._process
        if process is None or process.poll() is not None:
            return

        if force:
            # ctrl+c sends SIGKILL to the process
            process.kill()
        else:
            # graceful shutdown with SIGTERM, then escalate to SIGKILL if it does not exit
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                warn("Alvie did not stop in time, forcing termination.\n")
                process.kill()
                process.wait()


class AlvieExecutionBuilder:
    """Builder for `AlvieExecution` instances."""

    def __init__(self) -> None:
        self._alvie_path: Path | None = None
        self._executable: str | None = None
        self._args: list[ConfigArg] = []
        self._is_raw_output: bool = False
        self._output_path: Path | None = None
        self._parsed_output_path: Path | None = None
        self._parallel: bool = False
        self._interactive: bool = False
        self._upload_name: str | None = None

    def with_alvie_path(self, alvie_path: Path) -> "AlvieExecutionBuilder":
        """Set the path to ALVIE."""
        self._alvie_path = alvie_path
        return self

    def with_executable(self, executable: str) -> "AlvieExecutionBuilder":
        """Set the name of the ALVIE executable to invoke."""
        self._executable = executable
        return self

    def with_args(self, args: list[ConfigArg]) -> "AlvieExecutionBuilder":
        """Set the execution arguments."""
        self._args = list(args)
        return self

    def add_arg(self, arg: ConfigArg) -> "AlvieExecutionBuilder":
        """Append a single argument to the execution."""
        self._args.append(arg)
        return self

    def raw_output(self, is_raw_output: bool = True) -> "AlvieExecutionBuilder":
        """Toggle raw (unparsed) output streaming."""
        self._is_raw_output = is_raw_output
        return self

    def with_output_path(self, output_path: Path | None) -> "AlvieExecutionBuilder":
        """Set the file the raw/formatted output is written to."""
        self._output_path = output_path
        return self

    def with_parsed_output_path(self, parsed_output_path: Path | None) -> "AlvieExecutionBuilder":
        """Set the file the parsed JSON output is saved to."""
        self._parsed_output_path = parsed_output_path
        return self

    def parallel(self, parallel: bool = True) -> "AlvieExecutionBuilder":
        """Mark the execution as part of a parallel batch."""
        self._parallel = parallel
        return self

    def interactive(self, interactive: bool = True) -> "AlvieExecutionBuilder":
        """Mark the execution as interactive."""
        self._interactive = interactive
        return self

    def with_upload_name(self, upload_name: str | None) -> "AlvieExecutionBuilder":
        """Set the filename the parsed output is stored under on the backend."""
        self._upload_name = upload_name
        return self

    def build(self) -> AlvieExecution:
        if self._alvie_path is None:
            raise ValueError("alvie_path is required to build an AlvieExecution.")
        if self._executable is None:
            raise ValueError("executable is required to build an AlvieExecution.")

        return AlvieExecution(
            alvie_path=self._alvie_path,
            executable=self._executable,
            args=self._args,
            is_raw_output=self._is_raw_output,
            output_path=self._output_path,
            parsed_output_path=self._parsed_output_path,
            parallel=self._parallel,
            interactive=self._interactive,
            upload_name=self._upload_name
        )
