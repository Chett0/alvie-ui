import argparse, subprocess
from dataclasses import dataclass, field
from io import TextIOWrapper
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
from pathlib import Path

from InquirerPy.prompts.list import ListPrompt
from InquirerPy.base.control import Choice


from tui.entities_flow import (
    Entity, 
    build_entity
)
from tui.executions_flow import (
    execute,
    build_commands,
    get_config_command,
    validate_config_command,
)
from tui.flow import is_debug_enabled
from execution.runner import (
    AlvieExecution,
    AlvieExecutionBuilder,
)
from execution.parallel import (
    merge_tmp_file,
    remove_tmp_files
)
from terminal.widgets import ParallelDashboard
from terminal.style import (
    DEBUG_PARSED_OUTPUT_ERROR,
    DEBUG_REQUIRES_RAW_OUTPUT_ERROR,
    banner
)

from config.paths import (
    get_alvie_code_path,
    json_output_path,
)

def run_parallel(
        output_path: Path | None,
        executions: list[AlvieExecution],
        njobs: int
):
    """Run Parallel execution: each execution writes to its own temp file, and every
       temp file is merged into the final output as soon as its run finishes
       (merge order follows completion order, not configuration order)."""
    tmp_dir = None
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_dir = output_path.parent / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
    
    for execution in executions:
        execution.parallel = True
        if tmp_dir:
            execution.output_path = tmp_dir / (
                f"{output_path.stem}.{uuid.uuid4().hex}.part" # type: ignore
            )

    print()
    dashboard = ParallelDashboard(
        [_execution_label(execution) for execution in executions]
    )

    def run_tracked(index: int, execution: AlvieExecution) -> None:
        dashboard.set_running(index)
        try:
            execution.run()
            dashboard.set_done(index)
        except BaseException:
            dashboard.set_failed(index)
            raise

    def run(merged : TextIOWrapper | None = None) -> None:
        """Run all executions in parallel, merging their outputs into `merged` as they complete."""
        with dashboard:
            
            # Build ALVIE executable before parallel running
            subprocess.run(
                ["dune", "build"],
                cwd=executions[0].alvie_path,
                check=True,
            )
            
            with ThreadPoolExecutor(max_workers=njobs) as executor:
                futures = {
                    executor.submit(run_tracked, index, execution): execution
                    for index, execution in enumerate(executions)
                }

                errors = []
                # Merge temp files as they complete, in completion order
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as exc:  # noqa: BLE001
                        errors.append((futures[future], exc))
                        continue
                    if merged:
                        merge_tmp_file(merged, futures[future].output_path)

                for execution, exc in errors:
                    print(f"\nError during execution of {execution.executable}: {exc}\n")   
                    
    try:
        if output_path:
            with output_path.open("w", encoding="utf-8") as merged:
                run(merged) 
        else:
            run()

        if output_path:
            print(f"\nAll executions completed. Merged output written to {output_path}\n")
        else:
            print("\nAll executions completed.")
            for execution in executions:
                if execution.parsed_output_path:
                    print(f"  Parsed output saved to {execution.parsed_output_path}")
            print()

    except Exception as e:
        print(f"\nError during execution: {e}\n")
        sys.exit(1)
    finally:
        remove_tmp_files(executions)
        


def _execution_label(execution: AlvieExecution, max_width: int = 48) -> str:
    """Build a short, single-line label describing an execution for the dashboard."""
    label = " ".join([execution.executable, *execution.args_string]).strip()
    if len(label) > max_width:
        label = label[: max_width - 1] + "…"
    return label


@dataclass
class CliArguments(argparse.Namespace):
    """Typed namespace holding every argument accepted by the non-interactive CLI."""

    configs: list[Path] = field(default_factory=list)
    raw_output: bool = False
    parsed_output: list[Path] | None = None
    output: Path | None = None
    njobs: int = 1
    interactive: bool = False
    name: list[str] | None = None

    @classmethod
    def parse(
        cls, 
        parser: argparse.ArgumentParser, 
        argv: list[str]
    ) -> "CliArguments":
        """Parse ``argv`` with ``parser`` into a typed ``CliArguments`` instance."""
        return parser.parse_args(argv, namespace=cls())

    def validate(
            self, 
            parser: argparse.ArgumentParser
    ) -> None:
        """Validate the parsed arguments"""
        if self.njobs < 1:
            parser.error("--njobs must be a positive integer")

        # interactive mode cannot be used with raw output (requires a refactor to support both)
        if self.interactive and self.raw_output:
            parser.error("--interactive cannot be used with --raw-output")

        # parallel execution requires at least one output file, terminal output is not supported
        if self.njobs > 1 and not self.parsed_output and not self.output and not self.interactive:
            parser.error("--njobs > 1 requires --output or --parsed-output or --interactive to be specified")

        if not self.configs:
            parser.error("No configuration files provided")
        if self.parsed_output and len(self.parsed_output) != len(self.configs):
            parser.error("The number of parsed-output paths must match the number of configuration files")

        if self.name and not self.interactive:
            parser.error("--name can only be used together with --interactive")


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the non-interactive CLI."""
    parser = argparse.ArgumentParser(
        prog="alvie-cli",
        description="Interface for the Alvie analysis tool. "
                    "Run with no arguments for the interactive mode, "
                    "or pass a saved configuration file to execute it directly.",
    )
    parser.add_argument(
        "configs",
        nargs="+",
        type=json_output_path,
        help="Paths to saved command configurations (JSON) to execute."
             "Default sequential execution"
    )
    parser.add_argument(
        "-r", "--raw-output",
        action="store_true",
        help="Stream the raw standard output instead of the parsed/formatted output",
    )
    # Mapping outputs to multiple configurations.
    #
    # The current implementation accepts one path per configuration and pairs `-o out1.json out2.json ...`
    # them positionally (configs[i] -> output[i]). It is validated below so the
    # number of paths must match the number of configs, and each is passed to the
    # matching AlvieExecution as `parsed_output_path`.
    #
    # Alternatives considered (not implemented):
    #   1) Output directory + derived names: `-o DIR`, each file named after the
    #      config stem (e.g. <config>.json). Scales to any N and is race-free under
    #      parallel runs, but same-stem configs collide and it needs a directory check.
    #   2) Single aggregated JSON: one `-o results.json` collecting every run into one
    #      document keyed by config. Great for comparing configs, but executions must
    #      return their document and the caller writes once (collect-then-write under
    #      --njobs).
    #   3) Filename template: `-o "out/{name}_{index}.json"` with placeholders
    #      substituted per execution. Most flexible from one argument, but more surface
    #      to document and validate.
    parser.add_argument(
        "-p", "--parsed-output",
        nargs="+",
        default=None,
        type=json_output_path,
        help="Paths to json files where the parsed output will be saved, one per "
             "configuration in the same order"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        type=Path,
        help="Path to file where the output will be saved (default: stdout)"
    )
    parser.add_argument(
        "--njobs",
        type=int,
        default=1,
        help="Number of configurations to run in parallel (default: 1)",
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="After running, upload each parsed output to the backend "
             "and print a link to open it in the Alvie viewer",
    )
    parser.add_argument(
        "-n", "--name",
        nargs="+",
        default=None,
        help="Names under which the parsed output is stored on the backend, one "
             "per configuration in the same order. Requires --interactive and, "
             "unlike --parsed-output, does not write a local file",
    )
    return parser


def run_non_interactive(argv: list[str]) -> None:
    parser = build_parser()
    args = CliArguments.parse(parser, argv)
    args.validate(parser)

    config_paths = [Path(config) for config in args.configs]
    for config_path in config_paths:
        if not config_path.is_file():
            parser.error(f"Configuration file not found: {config_path}")

    build_commands()

    alvie_path = get_alvie_code_path()

    executions: list[AlvieExecution] = []
    for i, config_path in enumerate(config_paths):
        try:
            config_command = get_config_command(config_path)
            command = validate_config_command(config_command)
        except ValueError as error:
            parser.error(f"{config_path}: {error}")

        if is_debug_enabled(config_command.args):
            if not args.raw_output:
                parser.error(f"{config_path}: {DEBUG_REQUIRES_RAW_OUTPUT_ERROR}")
            if args.parsed_output:
                parser.error(f"{config_path}: {DEBUG_PARSED_OUTPUT_ERROR}")

        parsed_output_path : Path | None = args.parsed_output[i] if args.parsed_output else None
        upload_name : str | None = None
        if args.name and len(args.name) > i:
            upload_name = args.name[i]
            
        executions.append(
            AlvieExecutionBuilder()
                .with_alvie_path(alvie_path)
                .with_executable(command.executable)
                .with_args(config_command.args)
                .raw_output(args.raw_output)
                .with_output_path(args.output)
                .with_parsed_output_path(parsed_output_path)
                .with_upload_name(upload_name)
                .interactive(args.interactive)
                .build()
        )

    # sequential execution
    if args.njobs == 1 or len(executions) == 1:
        for execution in executions:
            execution.run_seq()
    else:
        run_parallel(
            output_path=args.output,
            executions=executions,
            njobs=args.njobs
        )


def run_interactive() -> None:
    banner()

    while True:
        choice = ListPrompt(
            message="What do you want to do:",
            choices=[
                Choice(value="execute", name="Execute a command")
            ] + [
                Choice(value=entity, name=f"Build {entity.value}")
                for entity in Entity
            ] + [
                Choice(value="exit", name="Exit")
            ]
        ).execute()

        if choice == "execute":
            execute()
        elif choice == "exit":
            return
        else:
            build_entity(choice)