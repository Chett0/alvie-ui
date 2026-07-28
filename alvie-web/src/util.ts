import symbolCatalog from './symbolCatalog'
import type {
  FilterValues,
  IndexedHypothesis,
  IndexedRun,
  Run,
  SelectOption,
} from './types'

export const symbolsToOptions = (
  symbols: Record<string, { name: string; color: string }>,
): SelectOption[] =>
  Object.entries(symbols).map(([key, { name: label, color }]) => ({
    value: key,
    label,
    color,
  }))

const matchesFilter = (selectedValues: string[], availableValues: string[]) =>
  selectedValues.length === 0 ||
  selectedValues.some((value) => availableValues.includes(value))

const stepMatchesFilters = (
  { inputs = [], outputs = [] }: Run[number],
  filters: FilterValues,
) => {
  const matchesActor = (actor?: string) =>
    filters.actors.length === 0 || Boolean(actor && filters.actors.includes(actor))

  const matchesInput = inputs.some(
    ({ actor, symbol }) =>
      matchesActor(actor) &&
      matchesFilter(filters.inputs, [symbol]),
  )

  const matchesOutput = outputs.some((symbol) => {
    const outputActor = symbolCatalog.outputs[symbol]?.actor

    return matchesActor(outputActor) && matchesFilter(filters.outputs, [symbol])
  })

  const hasInputFilters = filters.inputs.length > 0
  const hasOutputFilters = filters.outputs.length > 0

  if (hasInputFilters && !matchesInput) return false
  if (hasOutputFilters && !matchesOutput) return false
  if (!hasInputFilters && !hasOutputFilters && filters.actors.length > 0) {
    return matchesInput || matchesOutput
  }

  return true
}

const runMatchesFilters = (run: IndexedRun, filters: FilterValues) =>
  run.steps.some((step) => stepMatchesFilters(step, filters))

const indexRun = (
  steps: Run,
  hypothesisIndex: number,
  runIndex: number,
): IndexedRun => {
  const inputSymbols = new Set<string>()
  const outputSymbols = new Set<string>()
  const inputActors = new Set<IndexedRun['actors'][number]>()

  for (const { inputs = [], outputs = [] } of steps) {
    for (const { symbol, actor } of inputs) {
      inputSymbols.add(symbol)
      if (actor) inputActors.add(actor)
    }

    for (const symbol of outputs) outputSymbols.add(symbol)
  }

  const inputs = [...inputSymbols]
  const outputs = [...outputSymbols]
  const actors = [
    ...new Set(
      [
        ...inputActors,
        ...outputs.map((symbol) => symbolCatalog.outputs[symbol]?.actor),
      ].filter(Boolean),
    ),
  ] as IndexedRun['actors']

  const details = [
    ...inputs.map((symbol) => symbolCatalog.inputs[symbol]),
    ...outputs.map((symbol) => symbolCatalog.outputs[symbol]),
  ]
  const detailText = details
    .filter(Boolean)
    .flatMap((detail) => [detail.name, detail.description])

  return {
    steps,
    index: runIndex,
    actors,
    inputSymbols: inputs,
    outputSymbols: outputs,

    // Example: "hypothesis 1 run 1 attacker enclave no actor sc u t † cstartcounting start the timer counter cubr unconditional branch exits enclave otime timed observation oillegal input not permitted"
    searchText: [
      `hypothesis ${hypothesisIndex + 1}`,
      `run ${runIndex + 1}`,
      ...actors,
      ...inputs,
      ...outputs,
      ...detailText,
    ].join(' ').toLowerCase(),
  }
}

export const indexHypotheses = (
  hypotheses: Run[][],
): IndexedHypothesis[] =>
  hypotheses.map((runs, index) => ({
    index,
    runs: runs.map((steps, runIndex) => indexRun(steps, index, runIndex)),
  }))

export const filterHypotheses = (
  hypotheses: IndexedHypothesis[],
  filters: FilterValues,
  searchRegex: RegExp | null,
): IndexedHypothesis[] => {
  const hasActiveFilters = Object.values(filters).some(
    (values) => values.length > 0,
  )

  if (!searchRegex && !hasActiveFilters) return hypotheses

  return hypotheses.flatMap(({ index, runs }) => {

    // filter runs based on search and filters
    const matchingRuns = runs.filter(
      (run) =>
        // search filter
        (!searchRegex || searchRegex.test(run.searchText)) &&

        // Dropdown filters must match the same step; the full matching run is still shown.
        (!hasActiveFilters || runMatchesFilters(run, filters)),
    )

    // [ [{index: 0, runs: [run1, run2]}], [{index: 1, runs: [run3]}], [] ] -- flatten --> [ {index: 0, runs: [run1, run2]}, {index: 1, runs: [run3]} ]
    return matchingRuns.length ? [{ index, runs: matchingRuns }] : []
  })
}
