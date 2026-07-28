from dataclasses import dataclass, field
from collections import Counter
from terminal.style import (
    color_from_sgr, 
    ACTORS, 
    RUN_SEPARATOR_RE, 
    COLOR_SEPARATOR_RE
)


@dataclass 
class SymbolParser:
    input_symbols: dict
    output_symbols: dict


@dataclass
class ParsedOutput:
    parsed_hypotheses: list["ParsedHypothesis"] = field(default_factory=list)
    output_counts: Counter[str] = field(default_factory=Counter)

    hypotheses_count: int = field(init=False, default=0)
    runs_count: int = field(init=False, default=0)
    steps_count: int = field(init=False, default=0)

    def format_recap(
        self,
        parser: SymbolParser
    ) -> str:
        """Format the total occurrences of number of hypotheses, runs, steps and output symbol."""
        
        lines = [
            "Recap\n",
            f"  - Hypotheses: {self.hypotheses_count}",
            f"  - Runs: {self.runs_count}",
            f"  - Steps: {self.steps_count}",
            "\n  - Outputs:",
        ]
        
        # show only output symbols with non-zero occurrences
        for symbol, data in parser.output_symbols.items():
            if self.output_counts[symbol] > 0:
                lines.append(f"    - {data['name']} ({symbol}): {self.output_counts[symbol]}")
        return "\n".join(lines) + "\n"


@dataclass 
class ParsedSymbol:
    symbol: str
    name: str
    description: str
    actor: str
    color: str | None

    # JSON parser: attacker, enclave share some input symbols, so we distinguish them by actor
    def to_input_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "actor": self.actor,
        }

    def format(self) -> str:
        """Format a parsed input or output symbol."""
        return f"{self.actor}: {self.name} ({self.symbol})"
    
    @classmethod
    def parse(
        cls,
        actor: str | None,
        color: str | None,
        symbol: str,
        symbol_data: dict,
    ) -> "ParsedSymbol":
        """Build a parsed symbol from the config entry and active ANSI color."""
        return ParsedSymbol(
            symbol=symbol,
            name=symbol_data["name"],
            description=symbol_data["description"],
            actor=actor or "Unknown actor",
            color=color,
        )


@dataclass
class ParsedStep:
    # create a new list for each instance
    # [] would create a single shared list by all instances
    inputs: list[ParsedSymbol] = field(default_factory=list)
    outputs: list[ParsedSymbol] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "inputs": [symbol.to_input_dict() for symbol in self.inputs],
            "outputs": [symbol.symbol for symbol in self.outputs],
        }
    
    def format(self) -> str:
        """Format a step containing several input and output symbols."""
        inputs = " & ".join(symbol.format() for symbol in self.inputs)
        outputs = " & ".join(symbol.format() for symbol in self.outputs)
        return f"\t{inputs} -> {outputs}\n\n"
    
    @classmethod
    def tokenize(
        cls,
        raw: str,
        parser: SymbolParser
    ) -> list[str]:
        """Split bracketed ALVIE text into delimiters and known symbols."""
        symbols = sorted(
            [*parser.input_symbols.keys(), *parser.output_symbols.keys()],
            key=len,
            reverse=True,
        )
        tokens: list[str] = []
        index = 0

        while index < len(raw):
            char = raw[index]

            if char.isspace():
                index += 1
                continue

            if char in "[]":
                tokens.append(char)
                index += 1
                continue

            match = next((symbol for symbol in symbols if raw.startswith(symbol, index)), None)
            if match:
                tokens.append(match)
                index += len(match)
                continue

            index += 1

        return tokens

@dataclass
class ParsedRun:
    steps: list[ParsedStep] = field(default_factory=list)

    def to_dict(self) -> list[dict]:
        return [step.to_dict() for step in self.steps]
    
    def format(self, number: int) -> str:
        """Format a parsed run for terminal output."""
        steps = "".join(step.format() for step in self.steps)
        return f"Run {number}:\n{steps}"
    
    @classmethod
    def parse(
        cls, 
        raw_run: str, 
        parser: SymbolParser,
        output: ParsedOutput
    ) -> "ParsedRun":
        """Parse one run containing several steps."""
        steps : list[ParsedStep] = []
        input_step : list[ParsedSymbol] = []
        output_step : list[ParsedSymbol] = []    
        actor: str | None = None
        color: str | None = None
        is_output = False

        # iterate over color codes and symbols in the raw run
        for sgr_code, text in COLOR_SEPARATOR_RE.findall(raw_run):
            if sgr_code:
                color = color_from_sgr(sgr_code)
                if not color:
                    continue
                
                actor = ACTORS[color]
            else:
                for token in ParsedStep.tokenize(
                    raw=text, 
                    parser=parser
                ):
                    if token == "[":
                        is_output = False
                        continue

                    if token == "]":
                        steps.append(ParsedStep(inputs=input_step.copy(), outputs=output_step.copy()))
                        input_step.clear()
                        output_step.clear()
                        actor = None
                        color = None
                        is_output = False
                        continue

                    if is_output:
                        output_symbol = parser.output_symbols.get(token, None)
                        if output_symbol:
                            output_step.append(
                                ParsedSymbol.parse(
                                    actor=actor, 
                                    color=color, 
                                    symbol=token, 
                                    symbol_data=output_symbol
                                ))
                            output.output_counts[token] += 1
                    else:
                        input_symbol = parser.input_symbols.get(token, None)
                        if input_symbol:
                            input_step.append(
                                ParsedSymbol.parse(
                                    actor=actor, 
                                    color=color, 
                                    symbol=token, 
                                    symbol_data=input_symbol
                                ))
                            is_output = True
    
        output.steps_count += len(steps)
        return ParsedRun(steps=steps)


@dataclass
class ParsedHypothesis:
    runs: list[ParsedRun] = field(default_factory=list)

    def to_dict(self) -> list[list[dict]]:
        return [run.to_dict() for run in self.runs]
    
    def format(self) -> str:
        """Format a parsed hypothesis for terminal output."""
        return "".join(
            run.format(run_number)
            for run_number, run in enumerate(self.runs, start=1)
        )
    
    @classmethod
    def parse(
        cls, 
        raw : str, 
        parser : SymbolParser,
        output: ParsedOutput
    ) -> "ParsedHypothesis":
        """Parse one hypothesis containing several runs."""
        runs: list[ParsedRun] = []

        raw_runs = [raw_run for raw_run in RUN_SEPARATOR_RE.split(raw) if raw_run]
        for raw_run in raw_runs:
            runs.append(ParsedRun.parse(
                raw_run=raw_run,
                parser=parser,
                output=output
            ))
        
        output.runs_count += len(runs)
        return ParsedHypothesis(runs=runs)