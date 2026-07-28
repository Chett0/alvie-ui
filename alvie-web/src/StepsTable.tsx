import { ActorBadge, SymbolBadge } from './Badges'
import symbolCatalog from './symbolCatalog'
import type { Actor, RunStep } from './types'

interface ActionDetailsProps {
  symbol: string
  details?: {
    name: string
    description: string
    color: string
  }
  color?: string
}

const inputColorForActor = (
  actor: Actor,
  catalogColor?: string,
): string | undefined => {
  if (actor === 'Enclave') return 'green'
  if (actor === 'Attacker') return catalogColor?.includes('red') ? 'red' : 'blue'
  return catalogColor
}

function ActionDetails({ symbol, details, color }: ActionDetailsProps) {
  return (
    <div className="step-action">
      <div className="d-flex align-items-center flex-wrap gap-2">
        <span className="fw-semibold">{details?.name ?? 'Unknown action'}</span>
        <SymbolBadge symbol={symbol} color={color ?? details?.color} />
      </div>

      <div className="small text-secondary mt-1">
        {details?.description ?? 'No description available'}
      </div>
    </div>
  )
}

function StepsTable({ steps }: { steps: RunStep[] }) {
  return (
    <div className="table-responsive border rounded-3">
      <table className="table steps-table align-middle mb-0">
        <caption className="visually-hidden">Run steps</caption>

        <colgroup>
          <col className="step-number-column" />
          <col className="input-actor-column" />
          <col className="input-action-column" />
          <col className="output-action-column" />
        </colgroup>

        <thead className="table-light">
          <tr>
            <th scope="col">#</th>
            <th scope="col">Input actor</th>
            <th scope="col">Input action</th>
            <th scope="col">Output action</th>
          </tr>
        </thead>

        <tbody>
          {steps.map((step, stepIndex) => {
            const inputs = step.inputs ?? []
            const outputs = step.outputs ?? []
            const outputRows = outputs.length ? outputs : [null]

            return outputRows.map((symbol, outputIndex) => {
              const isFirstOutput = outputIndex === 0
              const outputDetails = symbol
                ? symbolCatalog.outputs[symbol]
                : undefined

              return (
                <tr key={`${stepIndex}-${symbol ?? 'empty'}-${outputIndex}`}>
                  {isFirstOutput && (
                    <>
                      <th scope="row" rowSpan={outputRows.length}>
                        {stepIndex + 1}
                      </th>

                      <td rowSpan={outputRows.length}>
                        <div className="step-stack">
                          {inputs.map((input, inputIndex) => (
                            <ActorBadge
                              actor={input.actor}
                              key={`${input.symbol}-${input.actor}-${inputIndex}`}
                            />
                          ))}
                        </div>
                      </td>

                      <td rowSpan={outputRows.length}>
                        <div className="step-stack">
                          {inputs.map((input, inputIndex) => (
                            <div
                              className="step-cell-item"
                              key={`${input.symbol}-${inputIndex}`}
                            >
                              <ActionDetails
                                symbol={input.symbol}
                                details={symbolCatalog.inputs[input.symbol]}
                                color={inputColorForActor(
                                  input.actor,
                                  symbolCatalog.inputs[input.symbol]?.color,
                                )}
                              />
                            </div>
                          ))}
                        </div>
                      </td>

                    </>
                  )}

                  <td>
                    {symbol ? (
                      <ActionDetails symbol={symbol} details={outputDetails} />
                    ) : (
                      <span className="text-secondary">No output</span>
                    )}
                  </td>
                </tr>
              )
            })
          })}
        </tbody>
      </table>
    </div>
  )
}

export default StepsTable;
