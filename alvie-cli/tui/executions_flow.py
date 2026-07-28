import json
import os
from pathlib import Path

from InquirerPy.prompts.fuzzy import FuzzyPrompt
from InquirerPy.base.control import Choice
from InquirerPy.prompts.list import ListPrompt
from InquirerPy.prompts.confirm import ConfirmPrompt
from InquirerPy.prompts.filepath import FilePathPrompt

from prompt_toolkit.validation import ValidationError

from .entities_flow import build_choices
from models.commands import Command, Argument, ConfigCommand
from config.paths import get_alvie_code_path, get_alvie_cli_path, validate_save_path
from config.loaders import load_args, load_commands
from execution.runner import AlvieExecution, DEBUG_PARSED_OUTPUT_ERROR
from tui.validators import FileExtensionValidator
from tui.choices import DONE_CHOICE, is_done
from tui.flow import (
    Flow, 
    StepOutput, 
    StepResult, 
    CommandState, 
    ConfigArg, 
    create_prompt, 
    is_debug_enabled
)


ALVIE_PATH = get_alvie_code_path()
ALVIE_CLI_PATH = get_alvie_cli_path()
commands_map : dict[str, Command] = {}


def build_commands() -> dict[str, Command]:
    global commands_map

    raw_commands : list = load_commands()
    raw_args : dict[str, dict] = load_args()
    
    commands : list[Command] = []
    
    # Load effective args
    for raw_command in raw_commands:
        
        cmd = {key: value for key, value in raw_command.items() if key in {"name", "description", "executable"}}
        cmd["args"] = []
        
        for arg in raw_command.get("args", []):
            cmd_arg = {"flag": arg}
            cmd_arg.update(raw_args.get(arg, {}))
            cmd["args"].append(Argument.model_validate(cmd_arg))
            
        commands.append(Command.model_validate(cmd))

    if not commands:
        raise RuntimeError("No commands found. Please check the configuration.")

    commands_map = {
        command.name : command
        for command in commands
    }

    return commands_map


def get_config_command(
        file_path : Path
) -> ConfigCommand:
    with file_path.open("r") as file:
        config_command = json.load(file)

    if not config_command:
        raise RuntimeError("No configuration command found.")
    
    command = ConfigCommand.model_validate(config_command)

    return command


def validate_config_command(config_command: ConfigCommand) -> Command:
    """
    Validate a loaded configuration against the known command/argument definitions.

    Returns the matched Command. Raises ValueError if the command is unknown or any flag/value pairing is inconsistent.
    """
    command : Command | None = commands_map.get(config_command.name)
    if not command:
        raise ValueError(f"Command {config_command.name} not found in the configuration.")

    for arg in config_command.args:
        command_arg : Argument | None = command.get_arg_by_flag(arg.flag)
        if not command_arg:
            raise ValueError(f"Argument {arg.flag} not found in command {config_command.name}.")

        if command_arg.requires_value():
            if arg.value is None:
                raise ValueError(f"Argument {arg.flag} has no value in the configuration.")

            try:
                command_arg.validate_value(arg.value)
            except ValidationError as error:
                raise ValueError(
                    f"Validation error for argument {arg.flag}: {error.message}"
                ) from error
        elif arg.value is not None:
            raise ValueError(f"Argument {arg.flag} is a flag and must not have a value.")

    return command



def select_args(state: CommandState) -> StepOutput:
    #TODO: add the opporunity to going back on args selection
    if not state.name:
        print("No command selected.")
        return StepOutput.back()

    command : Command | None = commands_map.get(state.name)
    if not command:
        print(f"Command {state.name} not found in the configuration.")
        return StepOutput.back()

    chosen_args : list[ConfigArg] = []

    required_args : list[Argument] = [
        arg for arg in command.args
        if arg.required and not arg.prefilled
    ]
    prefilled_args : list[Argument] = [
        arg for arg in command.args
        if arg.required and arg.prefilled and arg.default is not None
    ]
    optional_args : list[Argument] = [
        arg for arg in command.args
        if not arg.required
    ]

    for arg in prefilled_args:
        chosen_args.append(ConfigArg(flag=arg.flag, value=arg.default))

    for arg in required_args: 
        result = collect_arg(arg, chosen_args)
        if result is StepResult.BACK:
            return StepOutput.back()
        
    while prefilled_args:
        choices = [
            Choice(value=index, name=f"{arg.description}: {arg.default}")
            for index, arg in enumerate(prefilled_args)
        ]

        arg = create_prompt(
            ListPrompt,
            message="Do you want to modify prefilled arguments?",
            choices=choices + [DONE_CHOICE]
        ).execute()

        if arg is StepResult.BACK:
            return StepOutput.back()

        if is_done(arg):
            break

        argument = prefilled_args[arg]
        result = collect_arg(argument, chosen_args)
        if result is StepResult.BACK:
            return StepOutput.back()

        prefilled_args.remove(argument)
        
    
    while optional_args:
        # I use index rather than the args because inquirerPy does a deep copy of choices
        optional_choices : list[Choice] = [
            Choice(value=index, name=arg.description) 
            for index, arg in enumerate(optional_args)
        ] 

        arg = create_prompt(
            ListPrompt,
            message="Do you want to provide optional arguments?",
            choices= optional_choices + [DONE_CHOICE]
        ).execute()

        if arg is StepResult.BACK:
            return StepOutput.back()

        if is_done(arg):
            break

        else:
            argument : Argument = optional_args[arg]
            result = collect_arg(argument, chosen_args)
            if result is StepResult.BACK:
                return StepOutput.back()
            optional_args.remove(argument)
    
    state.args = chosen_args
    return StepOutput.next("select_dump")


def collect_arg(arg: Argument, args: list[ConfigArg]) -> StepResult | None:
    value = arg.select_value()
    if value is StepResult.BACK:
        return StepResult.BACK

    args[:] = [existing for existing in args if existing.flag != arg.flag]

    if isinstance(value, bool):
        if value:
            args.append(ConfigArg(flag=arg.flag))
    else:
        args.append(ConfigArg(flag=arg.flag, value=value))


def select_config(state: CommandState) -> StepOutput:
    file = create_prompt(
            FilePathPrompt,
            message="Select the configuration file for the command:",
            default=f"{ALVIE_CLI_PATH}/presets/config.json",
            validate=FileExtensionValidator.json_file_validator(must_exists=True),
        ).execute()

    if file is StepResult.BACK:
        return StepOutput.back()

    file_path : Path = Path(file)
    config_command : ConfigCommand = get_config_command(file_path)

    try:
        validate_config_command(config_command)
    except ValueError as error:
        print(error)
        return StepOutput.stay()

    state.args = [
        ConfigArg(flag=arg.flag, value=arg.value)
        for arg in config_command.args
    ]
    state.executable = config_command.executable
    state.name = config_command.name

    return StepOutput.next(next_step="select_output_mode")


def branch_config(state: CommandState) -> StepOutput:
    config = create_prompt(
        ConfirmPrompt,
        allow_back=True,
        message="Do you want to use a configuration?",
        default=True
    ).execute()

    if config is StepResult.BACK:
        return StepOutput.back()

    if config:
        return StepOutput.next("select_config")
    else:
        return StepOutput.next("select_command")


def select_output_mode(state: CommandState) -> StepOutput:
    raw_output = create_prompt(
        ConfirmPrompt,
        allow_back=True,
        message="Do you want to see the standard raw output of the command?",
        default=False,
    ).execute()
    
    if raw_output is StepResult.BACK:
        return StepOutput.back()
    
    state.raw_output = raw_output
    if not state.raw_output:
        return StepOutput.next(next_step="select_json_output_path")
    
    return StepOutput.next(next_step="execute_alvie")
    

def select_json_output_path(state: CommandState) -> StepOutput:
    if is_debug_enabled(state.args):
        print(DEBUG_PARSED_OUTPUT_ERROR)
        return StepOutput.back()

    parsed_output_path : Path | None = validate_save_path(
        message="Where do you want to save parsed output JSON?",
        default_path=f"{ALVIE_CLI_PATH}/parsed-output/parsed_output.json",
        validator=FileExtensionValidator.json_file_validator()
    )

    if parsed_output_path is StepResult.BACK:
        return StepOutput.back()

    state.parsed_output_path = parsed_output_path
    return StepOutput.next(next_step="execute_alvie")


def execute_alvie(state: CommandState) -> StepOutput:
    if not state.executable:
        return StepOutput.back()

    AlvieExecution(
        alvie_path=ALVIE_PATH,
        executable=state.executable,
        args=state.args,
        is_raw_output=state.raw_output,
        parsed_output_path=state.parsed_output_path,
    ).run_seq()

    return StepOutput.next()


def select_command(state: CommandState) -> StepOutput:
    choices : list[Choice] = build_choices(
        items=list(commands_map.values()),
        extra_choices=[DONE_CHOICE]
    )

    action = create_prompt(
            FuzzyPrompt,
            allow_back=True,
            message="Select a command to execute:",
            choices=choices
    ).execute()

    if action is StepResult.BACK:
        return StepOutput.back()

    if is_done(action):
        return StepOutput.next()
    
    state.name = action.name
    state.executable = action.executable

    return StepOutput.next(next_step="select_args")


def select_dump(state: CommandState) -> StepOutput:
    dump_config : bool = create_prompt(
            ConfirmPrompt,
            allow_back=True,
            message="Do you want to save this configuration?",
            default=True,
        ).execute()

    if dump_config is StepResult.BACK:
        return StepOutput.back()
    
    if dump_config:
        return StepOutput.next(next_step="select_dump_path")
    else:
        return StepOutput.next(next_step="select_output_mode")


def select_dump_path(state: CommandState) -> StepOutput:
    WORKING_PATH = os.environ.get("WORKING_PATH", "/home/alvie/alvie-cli")
            
    # use create prompt in validate_save_path to allow back navigation
    config_path = validate_save_path(
        message="Select the path where to save the configuration:",
        default_path=f"{WORKING_PATH}/presets/config.json",
        validator=FileExtensionValidator.json_file_validator()
    )
    
    if config_path:
        with open(config_path, "w") as config_file:
            json.dump({
                "name" : state.name,
                "executable" : state.executable,
                "args": [
                    {"flag": arg.flag, "value": arg.value}
                    if arg.value is not None
                    else {"flag": arg.flag}
                    for arg in state.args
                ]
            }, config_file, indent=2)
        print(f"Configuration saved to {config_path}")

    return StepOutput.next(next_step="select_output_mode")


def execute() -> None:
    build_commands()

    flow = Flow(
        steps={
            "branch_config": branch_config,
            "select_config": select_config,
            "select_command": select_command,
            "select_args": select_args,
            "select_dump": select_dump,
            "select_dump_path": select_dump_path,
            "select_output_mode": select_output_mode,
            "select_json_output_path": select_json_output_path,
            "execute_alvie": execute_alvie,
        },
        root="branch_config",
        initial_state=CommandState()
    )
    flow.run()

    
