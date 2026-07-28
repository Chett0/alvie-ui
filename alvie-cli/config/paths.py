import argparse
import os

from pathlib import Path
from dotenv import load_dotenv

from InquirerPy.prompts.filepath import FilePathPrompt
from InquirerPy.prompts.confirm import ConfirmPrompt
from prompt_toolkit.document import Document
from prompt_toolkit.validation import ValidationError

from tui.validators import FileExtensionValidator

load_dotenv()

def get_alvie_code_path() -> Path:
    alvie_code_path = os.environ["ALVIE_CODE_PATH"]

    if not alvie_code_path:
        raise EnvironmentError(
            "ALVIE_CODE_PATH environment variable is not set. Please set it to the path of the Alvie codebase."
        )

    return Path(alvie_code_path).expanduser().resolve()

def get_alvie_cli_path() -> Path:
    alvie_cli_path = os.environ["ALVIE_CLI_PATH"]
    
    if not alvie_cli_path:
        raise EnvironmentError(
            "ALVIE_CLI_PATH environment variable is not set. Please set it to the path of the Alvie CLI."
        )
        
    return Path(alvie_cli_path).expanduser().resolve()
    
def validate_save_path(
    message: str,
    default_path: str,
    validator=None
) -> Path | None:
    """
    Ask the user a save path for a new file.
    Manage overwrite and parent directory creation.
    Return the path of the saved file or None if the user decide to cancel the operation.
    """
    while True:
        output_path: str = FilePathPrompt(
            message=message,
            default=default_path,
            validate=validator
        ).execute()
        
        path = Path(output_path)
        
        if path.exists():
            overwrite = ConfirmPrompt(
                message=f"File '{path.name}' already exists. Overwrite?",
                default=True
            ).execute()

            if not overwrite:
                print("Please choose another file path.")
                continue  # Insert another path
                
        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    

def json_output_path(value: str) -> Path:
    """Validate a JSON output"""
    try:
        FileExtensionValidator.json_file_validator().validate(Document(value))
    except ValidationError as error:
        raise argparse.ArgumentTypeError(error.message)
    return Path(value)