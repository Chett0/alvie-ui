from enum import Enum
from typing_extensions import Self
from pydantic import BaseModel, Field, PrivateAttr, model_validator

from prompt_toolkit.validation import Validator
from prompt_toolkit.document import Document

from InquirerPy.prompts.input import InputPrompt
from InquirerPy.prompts.filepath import FilePathPrompt
from InquirerPy.prompts.list import ListPrompt
from InquirerPy.base.control import Choice
from InquirerPy.prompts.confirm import ConfirmPrompt

from models.instructions import BaseChoice
from tui.validators import (
    FileExtensionValidator, 
    DirectoryValidator, 
    HashValidator, 
    IntValidator, 
    FloatValidator,
    ValuesValidator, 
    HexValidator
)
from tui.flow import (
    create_prompt, 
    ConfigArg
)

class InputType(Enum):
    FILENAME = "filename"
    DIRECTORY = "directory"
    CHOICE = "choice"
    BOOLEAN = "boolean"
    INT = "int"
    FLOAT = "float"
    HEX = "hex"
    HASH = "hash"

class Validation(BaseModel):
    must_exists: bool = True

# TODO: superclass for different types (filename has extension required, ...)
class Argument(BaseModel):
    flag: str
    type: InputType
    description: str
    extension : str | None = None
    validation: Validation | None = None
    values : list[str] | None = None
    default: str | None = None
    required: bool = False
    prefilled: bool = False

    _validator: Validator | None = PrivateAttr(default=None)

    @model_validator(mode="after")
    def populate_validator(self) -> Self:

        match self.type:
            case InputType.FILENAME:
                if self.extension and not self.extension.startswith("."):
                    self.extension = f".{self.extension}"
                
                must_exists = self.validation.must_exists if self.validation else True
                self._validator = FileExtensionValidator(
                    expected_extension=self.extension,
                    must_exists=must_exists
                )
            case InputType.DIRECTORY:
                must_exists = self.validation.must_exists if self.validation else True
                self._validator = DirectoryValidator(
                    must_exists=must_exists
                )

            case InputType.INT:
                self._validator = IntValidator()

            case InputType.FLOAT:
                self._validator = FloatValidator()

            case InputType.CHOICE:
                if not self.values:
                    raise ValueError(f"Argument {self.flag} is of type choice but no values were provided.")

                self._validator = ValuesValidator(
                    values=self.values 
                )
            case InputType.HEX:
                self._validator = HexValidator()
            
            case InputType.HASH:
                self._validator = HashValidator()

        return self

    def select_value(self, allow_back: bool = True):
        message : str = f"{self.description} {'(required)' if self.required else '(optional)'}:"
        
        match self.type:
            case InputType.FILENAME | InputType.DIRECTORY:
                prompt = create_prompt(
                    FilePathPrompt,
                    allow_back=allow_back,
                    message=message,
                    default=self.default,
                    validate=self._validator
                )
        
            case InputType.CHOICE:
                if not self.values:
                    raise ValueError(f"Argument {self.flag} is of type choice but no values were provided.")
                
                choices = [Choice(value=value, name=value) for value in self.values]

                prompt = create_prompt(
                    ListPrompt,
                    allow_back=allow_back,
                    message=message,
                    choices=choices
                )
        
            case InputType.BOOLEAN:
                prompt = create_prompt(
                    ConfirmPrompt,
                    allow_back=allow_back,
                    message=message,
                    default=True
                )
        
            case InputType.INT | InputType.HEX:
                prompt = create_prompt(
                    InputPrompt,
                    allow_back=allow_back,
                    message=message,
                    default=self.default,
                    validate=self._validator
                )

            case _:
                raise ValueError(f"Argument {self.flag} has unknown type {self.type}.")
            
        return prompt.execute()

    def validate_value(self, value: str) -> None:
        if self._validator:
            document = Document(text=value)
            self._validator.validate(document=document)
    
    def requires_value(self) -> bool:
        return self.type != InputType.BOOLEAN


class Command(BaseChoice):
    executable: str
    args: list[Argument] = Field(default_factory=list)
    
    def get_arg_by_flag(self, flag: str) -> Argument | None:
        for arg in self.args:
            if arg.flag == flag:
                return arg
            
        return None


class ConfigCommand(BaseModel):
    name: str
    executable: str
    args: list[ConfigArg] = Field(default_factory=list)
