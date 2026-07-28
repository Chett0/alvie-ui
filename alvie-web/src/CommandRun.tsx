import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import type { CommandArgument } from './types'

const RUN_DIRECTORY = '/home/alvie/alvie/code'

// encode special chars for bash
const quoteArgument = (value: string) =>
  /^[\w./:=+@%-]+$/.test(value)
    ? value
    : `'${value.replaceAll("'", `'"'"'`)}'`

const buildCommand = (
  executable: string,
  args: CommandArgument[] = [],
): string => {
  const commandParts = [
    `dune exec ${executable} --`,
    ...args.map(({ flag, value }) =>
      value === undefined || value === null || value === ''
        ? flag
        : `${flag} ${quoteArgument(String(value))}`,
    ),
  ]

  return commandParts
    .map((part, index) => {
      const indentation = index === 0 ? '' : '  '
      const continuation = index < commandParts.length - 1 ? ' \\' : ''

      return `${indentation}${part}${continuation}`
    })
    .join('\n')
}

const formatTimestamp = (timestamp: string) =>
  timestamp ? timestamp.replace('T', ' ').replace(/\.\d+$/, '') : '—'

const getDuration = (start: string, end: string) => {
  const durationMilliseconds = Date.parse(end) - Date.parse(start)

  return Number.isFinite(durationMilliseconds)
    ? `${(durationMilliseconds / 1000).toFixed(1)}s`
    : '—'
}

function CopyIcon({ copied }: { copied: boolean }) {
  return copied ? (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="18"
      height="18"
      fill="currentColor"
      viewBox="0 0 16 16"
      aria-hidden="true"
    >
      <path d="M9.5 0a.5.5 0 0 1 .5.5.5.5 0 0 0 .5.5.5.5 0 0 1 .5.5V2a.5.5 0 0 1-.5.5h-5A.5.5 0 0 1 5 2v-.5a.5.5 0 0 1 .5-.5.5.5 0 0 0 .5-.5.5.5 0 0 1 .5-.5z" />
      <path d="M3 2.5a.5.5 0 0 1 .5-.5H4a.5.5 0 0 0 0-1h-.5A1.5 1.5 0 0 0 2 2.5v12A1.5 1.5 0 0 0 3.5 16h9a1.5 1.5 0 0 0 1.5-1.5v-12A1.5 1.5 0 0 0 12.5 1H12a.5.5 0 0 0 0 1h.5a.5.5 0 0 1 .5.5v12a.5.5 0 0 1-.5.5h-9a.5.5 0 0 1-.5-.5z" />
      <path d="M10.854 7.854a.5.5 0 0 0-.708-.708L7.5 9.793 6.354 8.646a.5.5 0 1 0-.708.708l1.5 1.5a.5.5 0 0 0 .708 0z" />
    </svg>
  ) : (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="18"
      height="18"
      fill="currentColor"
      viewBox="0 0 16 16"
      aria-hidden="true"
    >
      <path d="M3.5 2a.5.5 0 0 0-.5.5v12a.5.5 0 0 0 .5.5h9a.5.5 0 0 0 .5-.5v-12a.5.5 0 0 0-.5-.5H12a.5.5 0 0 1 0-1h.5A1.5 1.5 0 0 1 14 2.5v12a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 2 14.5v-12A1.5 1.5 0 0 1 3.5 1H4a.5.5 0 0 1 0 1z" />
      <path d="M10 .5a.5.5 0 0 0-.5-.5h-3a.5.5 0 0 0-.5.5.5.5 0 0 1-.5.5.5.5 0 0 0-.5.5V2a.5.5 0 0 0 .5.5h5A.5.5 0 0 0 11 2v-.5a.5.5 0 0 0-.5-.5.5.5 0 0 1-.5-.5" />
    </svg>
  )
}

const writeToClipboard = (text: string) => navigator.clipboard.writeText(text)

interface CopyButtonProps {
  value: string
  label: string
  className?: string
  children?: ReactNode
}

function CopyButton({
  value,
  label,
  className = '',
  children,
}: CopyButtonProps) {
  const [copyStatus, setCopyStatus] = useState('Copy')

  useEffect(() => {
    if (copyStatus === 'Copy') return undefined

    const timeoutId = window.setTimeout(() => setCopyStatus('Copy'), 2000)
    return () => window.clearTimeout(timeoutId)
  }, [copyStatus])

  const copyValue = async () => {
    try {
      await writeToClipboard(value)
      setCopyStatus('Copied')
    } catch (error) {
      console.error(`Unable to copy ${label}:`, error)
      setCopyStatus('Copy failed')
    }
  }

  const accessibleLabel =
    copyStatus === 'Copy' ? `Copy ${label}` : `${label}: ${copyStatus}`

  const variantClass = children
    ? copyStatus === 'Copied'
      ? 'btn-link text-success'
      : copyStatus === 'Copy failed'
        ? 'btn-link text-danger'
        : 'btn-link text-secondary'
    : copyStatus === 'Copy failed'
      ? 'btn-outline-danger'
      : 'btn-outline-secondary'

  return (
    <button
      className={`btn btn-sm ${className} ${variantClass}`}
      type="button"
      onClick={() => void copyValue()}
      aria-label={accessibleLabel}
      title={accessibleLabel}
    >
      {children ?? <CopyIcon copied={copyStatus === 'Copied'} />}
    </button>
  )
}

interface CommandRunProps {
  executable: string
  args: CommandArgument[]
  start: string
  end: string
}

function CommandRun({ executable, args, start, end }: CommandRunProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [needsExpansion, setNeedsExpansion] = useState(false)
  const commandCodeRef = useRef<HTMLPreElement | null>(null)
  const command = buildCommand(executable, args)

  useLayoutEffect(() => {
    if (isExpanded || !commandCodeRef.current) return undefined

    const commandCode = commandCodeRef.current
    const measureOverflow = () => {
      setNeedsExpansion(commandCode.scrollHeight > commandCode.clientHeight)
    }

    measureOverflow()
    const resizeObserver = new ResizeObserver(measureOverflow)
    resizeObserver.observe(commandCode)

    return () => resizeObserver.disconnect()
  }, [command, isExpanded])

  const timingDetails = [
    { label: 'Start', value: formatTimestamp(start) },
    { label: 'End', value: formatTimestamp(end) },
    { label: 'Duration', value: getDuration(start, end) },
  ]

  return (
    <section className="card shadow-sm mb-4" aria-labelledby="command-run-title">
      <div className="card-body">
        <div className="row g-3 align-items-stretch">
          <div className="col-12 col-lg-8 d-flex flex-column">
            <h2
              className="small fw-semibold text-secondary mb-1"
              id="command-run-title"
            >
              Command
            </h2>

            <div
              className={`command-preview border rounded-3 bg-body-tertiary p-3 pe-5 flex-grow-1 ${
                needsExpansion ? 'has-overflow' : ''
              }`}
            >
              <pre
                className={`command-code mb-0 ${!isExpanded ? 'is-collapsed' : ''}`}
                ref={commandCodeRef}
              >
                <code>{command}</code>
              </pre>

              <CopyButton
                value={command}
                label="command"
                className="command-copy-button"
              />

              {needsExpansion && (
                <button
                  className="btn btn-link btn-sm command-expand-button"
                  type="button"
                  onClick={() => setIsExpanded((current) => !current)}
                  aria-expanded={isExpanded}
                >
                  {isExpanded ? 'Show less' : 'Show full command'}
                </button>
              )}
            </div>
          </div>

          <div className="col-12 col-lg-4 d-flex">
            <div className="d-flex flex-column justify-content-between gap-2 w-100">
              {timingDetails.map(({ label, value }) => (
                <div key={label}>
                  <div className="small fw-semibold text-secondary mb-1">
                    {label}
                  </div>
                  <div className="border rounded-3 bg-body-tertiary px-3 py-2">
                    {value}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="row">
          <div className="col-12 col-lg-8">
            <p className="small text-secondary d-flex align-items-center gap-2 mt-2 mb-0">
              <span>Run from</span>
              <CopyButton
                value={RUN_DIRECTORY}
                label="run directory"
                className="command-path-copy-text"
              >
                <code>{RUN_DIRECTORY}</code>
              </CopyButton>
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}

export default CommandRun;