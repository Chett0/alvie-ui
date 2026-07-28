from pathlib import Path

from InquirerPy.separator import Separator
from InquirerPy.base.control import Choice
from prompt_toolkit.document import Document
from prompt_toolkit.validation import Validator, ValidationError

import re

from models.instructions import Operand

class FileExtensionValidator(Validator):

    def __init__(self, expected_extension: str | None = None, must_exists: bool = True):
        self.expected_extension = expected_extension
        self.must_exists = must_exists

    def validate(self, document : Document) -> None:
        path = Path(document.text)
        if self.must_exists and not path.is_file():
            raise ValidationError(
                message="Input is not a valid file path",
                cursor_position=document.cursor_position
            )
        if self.expected_extension and path.suffix != self.expected_extension:
            raise ValidationError(
                message=f"Input file must have extension {self.expected_extension}",
                cursor_position=document.cursor_position
            ) 
        
    @classmethod
    def attacker_file_validator(cls : type["FileExtensionValidator"], must_exists: bool = False) -> "FileExtensionValidator":
        return cls(
            expected_extension=".atdl",
            must_exists=must_exists
        )
    
    @classmethod
    def enclave_file_validator(cls : type["FileExtensionValidator"], must_exists: bool = False) -> "FileExtensionValidator":
        return cls(
            expected_extension=".etdl",
            must_exists=must_exists
        )

    @classmethod
    def json_file_validator(cls : type["FileExtensionValidator"], must_exists: bool = False) -> "FileExtensionValidator":
        return cls(
            expected_extension=".json",
            must_exists=must_exists
        )



class DirectoryValidator(Validator):

    def __init__(self, must_exists: bool = True):
        self.must_exists = must_exists

    def validate(self, document : Document) -> None:
        path = Path(document.text)
        if self.must_exists and not path.is_dir():
            raise ValidationError(
                message="Input is not a valid directory path",
                cursor_position=document.cursor_position
            )
        
class IntValidator(Validator):

    def __init__(self):
        pass

    def validate(self, document : Document) -> None:
        if not document.text.isdigit():
            raise ValidationError(
                message="Input must be an integer",
                cursor_position=document.cursor_position
            )
            
class FloatValidator(Validator):

    def __init__(self):
        pass

    def validate(self, document : Document) -> None:
        try:
            float(document.text)
        except ValueError:
            raise ValidationError(
                message="Input must be a float",
                cursor_position=document.cursor_position
            )
            
class HexValidator(Validator):
    def __init__(self):
        pass
    def validate(self, document: Document) -> None:
        text = document.text.strip()
        try:
            bytes.fromhex(text)
        except ValueError:
            raise ValidationError(
                message="Input must be a 32-character hexadecimal value",
                cursor_position=document.cursor_position
            )

# Commit hash: hex string of length between 7 (short commit) and 40 (full commit)
class HashValidator(Validator):
    def __init__(self):
        pass

    def validate(self, document: Document) -> None:
        text = document.text.strip()
        res = re.fullmatch(r"[0-9a-fA-F]{7,40}", text)
        if not res:
            raise ValidationError(
                message="Input must be a valid hexadecimal string of length between 7 and 40 characters",
                cursor_position=document.cursor_position
            )

class ParameterValidator(Validator):

    def __init__(self, operand_types: list[Operand]):
        self.operand_types = operand_types

    def validate(self, document: Document) -> None:
        
        for operand_type in self.operand_types:
            if operand_type.is_valid(document.text):
                return
            
        raise ValidationError(
            # message=f"Input does not match any of the expected operand types: {', '.join([operand_type.value for operand_type in self.operand_types])}",
            message=f"Input does not match any of the expected operand types",
            cursor_position=document.cursor_position
        )
    

class ChoiceValidator(Validator):
    """Validator for general choice prompts. Used for validation on FuzzyPrompt"""

    def __init__(self, choices: list[Choice]):
        self.choices_values = [
            choice.value 
            for choice in choices
            if not isinstance(choice, Separator) # ignore separators
        ]

    def validate(self, document: Document) -> None:
        if document.text not in self.choices_values:
            raise ValidationError(
                message="Please select a valid instruction from the list",
                cursor_position=document.cursor_position,
            )


class ValuesValidator(Validator):
    """Validator for choice arguments"""

    def __init__(self, values: list[str]):
        self.values : list = values

    def validate(self, document: Document) -> None:
        if document.text not in self.values:
            raise ValidationError(
                message=f"Input {document.text} does not match any of the expected values",
                cursor_position=document.cursor_position
            )