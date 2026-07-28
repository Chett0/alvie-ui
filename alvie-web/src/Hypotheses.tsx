import { useEffect, useState } from 'react'
import HypothesisCard from './HypothesisCard'
import RunCard from './RunCard'
import StepsTable from './StepsTable'
import type { IndexedHypothesis } from './types'

const HYPOTHESES_PER_PAGE = 5
const RUNS_PER_PAGE = 10

interface PaginatedHypothesisProps {
  runs: IndexedHypothesis['runs']
  hypothesisIndex: number
}

function PaginatedHypothesis({
  runs,
  hypothesisIndex,
}: PaginatedHypothesisProps) {
  const [page, setPage] = useState(1)
  const totalPages = Math.max(1, Math.ceil(runs.length / RUNS_PER_PAGE))
  const safePage = Math.min(page, totalPages)

  useEffect(() => {
    setPage(1)
  }, [runs])

  const startIndex = (safePage - 1) * RUNS_PER_PAGE
  const visibleRuns = runs.slice(startIndex, startIndex + RUNS_PER_PAGE)

  return (
    <HypothesisCard
      index={hypothesisIndex}
      runCount={runs.length}
      defaultOpen={false}
    >
      {visibleRuns.map(({ steps, index: runIndex }) => (
        <RunCard
          index={runIndex}
          stepCount={steps.length}
          defaultOpen={false}
          key={runIndex}
        >
          <StepsTable steps={steps} />
        </RunCard>
      ))}

      {totalPages > 1 && (
        <div className="d-flex justify-content-between align-items-center pt-2">
          <button
            className="btn btn-sm btn-outline-primary"
            type="button"
            disabled={safePage === 1}
            onClick={() => setPage(safePage - 1)}
          >
            Previous runs
          </button>

          <span className="small text-secondary">
            Runs {startIndex + 1}-
            {Math.min(startIndex + RUNS_PER_PAGE, runs.length)} of {runs.length}
          </span>

          <button
            className="btn btn-sm btn-outline-primary"
            type="button"
            disabled={safePage === totalPages}
            onClick={() => setPage(safePage + 1)}
          >
            Next runs
          </button>
        </div>
      )}
    </HypothesisCard>
  )
}

interface HypothesesProps {
  hypotheses: IndexedHypothesis[]
  page: number
  onPageChange: (page: number) => void
  emptyMessage?: string
}

function Hypotheses({
  hypotheses,
  page,
  onPageChange,
  emptyMessage = '',
}: HypothesesProps) {
  if (hypotheses.length === 0) {
    return emptyMessage ? (
      <div className="alert alert-info" role="status">
        {emptyMessage}
      </div>
    ) : null
  }

  const totalPages = Math.max(
    1,
    Math.ceil(hypotheses.length / HYPOTHESES_PER_PAGE),
  )
  const safePage = Math.min(page, totalPages)
  const startIndex = (safePage - 1) * HYPOTHESES_PER_PAGE
  const visibleHypotheses = hypotheses.slice(
    startIndex,
    startIndex + HYPOTHESES_PER_PAGE,
  )

  return (
    <>
      {visibleHypotheses.map(({ runs, index }) => (
        <PaginatedHypothesis
          runs={runs}
          hypothesisIndex={index}
          key={index}
        />
      ))}

      {totalPages > 1 && (
        <nav
          className="row g-0 align-items-center my-4"
          aria-label="Hypotheses pagination"
        >
          <div className="col-4">
            <button
              className="btn btn-outline-primary"
              type="button"
              disabled={safePage === 1}
              onClick={() => onPageChange(safePage - 1)}
            >
              Previous
            </button>
          </div>

          <span className="col-4 text-center">
            Page {safePage} of {totalPages}
          </span>

          <div className="col-4 text-end">
            <button
              className="btn btn-outline-primary"
              type="button"
              disabled={safePage === totalPages}
              onClick={() => onPageChange(safePage + 1)}
            >
              Next
            </button>
          </div>
        </nav>
      )}
    </>
  )
}

export default Hypotheses;
