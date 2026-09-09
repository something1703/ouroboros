import { useEffect, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import * as pdfjsLib from "pdfjs-dist"
import type { PDFDocumentProxy } from "pdfjs-dist"
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url"
import { getAssetFile, getAssetTimeline } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import type { RiskLevel, TimelineClaim } from "@/api/types"

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl

const RISK_RANK: Record<RiskLevel, number> = { blocking: 0, high: 1, medium: 2, low: 3, none: 4 }

// Signal Red only, per DESIGN.md -- the brand accent is not a risk-severity color.
function riskColor(level: RiskLevel | null): string {
  if (level === "blocking" || level === "high") return "var(--destructive)"
  return "var(--muted-foreground)"
}

function pageRisk(claims: TimelineClaim[]): RiskLevel | null {
  let worst: RiskLevel | null = null
  for (const claim of claims) {
    if (claim.risk_level == null) continue
    if (worst == null || RISK_RANK[claim.risk_level] < RISK_RANK[worst]) worst = claim.risk_level
  }
  return worst
}

function PdfPage({
  pdf,
  pageNumber,
  claims,
  onPin,
}: {
  pdf: PDFDocumentProxy
  pageNumber: number
  claims: TimelineClaim[]
  onPin: (claimId: string) => void
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      const page = await pdf.getPage(pageNumber)
      const viewport = page.getViewport({ scale: 1.2 })
      const canvas = canvasRef.current
      if (!canvas || cancelled) return
      canvas.width = viewport.width
      canvas.height = viewport.height
      const ctx = canvas.getContext("2d")
      if (!ctx) return
      await page.render({ canvasContext: ctx, viewport, canvas }).promise
    })()
    return () => {
      cancelled = true
    }
  }, [pdf, pageNumber])

  const risk = pageRisk(claims)

  return (
    <div className="flex flex-col gap-3 lg:flex-row">
      <div className="flex-1">
        <canvas ref={canvasRef} className="max-w-full rounded-md border border-border" />
      </div>
      {/* No fixed-width rail when a page has no claims -- an empty 192px column
          running the full document was the previous default. */}
      {claims.length > 0 && (
        <div className="w-full space-y-1.5 pt-1 lg:w-48 lg:shrink-0">
          <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <span>
              Page <span className="font-mono">{pageNumber}</span>
            </span>
            {risk && (
              <span
                className="size-1.5 rounded-full"
                style={{ backgroundColor: riskColor(risk) }}
                aria-hidden
              />
            )}
          </p>
          {claims.map((claim) => (
            <button
              key={claim.claim_id}
              type="button"
              onClick={() => onPin(claim.claim_id)}
              className="flex w-full items-start gap-1.5 rounded-md px-1.5 py-1 text-left text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              <span
                className="mt-1.5 size-1.5 shrink-0 rounded-full"
                style={{ backgroundColor: riskColor(claim.risk_level) }}
                aria-hidden
              />
              <span className="truncate">{claim.claim_text}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export function ScriptView({
  assetId,
  onSelectClaim,
}: {
  assetId: string
  onSelectClaim: (claimId: string) => void
}) {
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [loadAttempt, setLoadAttempt] = useState(0)

  const fileQuery = useQuery({
    queryKey: ["asset-file", assetId],
    queryFn: () => getAssetFile(assetId),
    // The signed URL is valid for an hour (EXPORT_URL_TTL server-side) -- without
    // this, React Query's default staleTime of 0 refetches on every remount/focus,
    // minting a fresh signed URL and re-running the pdf.js load below each time.
    // Found live: two back-to-back CORS failures a few seconds apart in the
    // console, each carrying a different signature -- not one failure logged
    // twice, but the fetch genuinely retried itself before the actual bug (no
    // CORS policy on the bucket) was fixed.
    staleTime: 5 * 60 * 1000,
  })
  const timelineQuery = useQuery({
    queryKey: ["asset-timeline", assetId],
    queryFn: () => getAssetTimeline(assetId),
  })

  useEffect(() => {
    if (!fileQuery.data) return
    let cancelled = false
    setLoadError(null)
    void pdfjsLib
      .getDocument({ url: fileQuery.data.url })
      .promise.then((doc) => {
        if (!cancelled) setPdf(doc)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        // A CORS/network failure throws a bare `TypeError: Failed to fetch` --
        // real, but not something a reader should have to parse. Anything else
        // (a genuinely malformed PDF, pdf.js's own parse errors) keeps its own
        // message, which is at least specific to what went wrong.
        const message =
          err instanceof TypeError
            ? "Couldn't reach the file. It may not have finished uploading, or the link expired."
            : err instanceof Error
              ? err.message
              : "Couldn't load this script."
        setLoadError(message)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- loadAttempt is a
    // deliberate manual retrigger, not a data dependency to react to on its own.
  }, [fileQuery.data, loadAttempt])

  const claimsByPage = new Map<number, TimelineClaim[]>()
  for (const claim of timelineQuery.data?.claims ?? []) {
    if (claim.page == null) continue
    const existing = claimsByPage.get(claim.page) ?? []
    existing.push(claim)
    claimsByPage.set(claim.page, existing)
  }

  if (fileQuery.isLoading || timelineQuery.isLoading) {
    return (
      <div className="space-y-3 p-6">
        <p className="text-sm text-muted-foreground">Loading script…</p>
        <Skeleton className="h-96 w-full" />
      </div>
    )
  }

  if (fileQuery.isError || loadError) {
    return (
      <div className="flex flex-col items-start gap-3 p-6">
        <p className="text-sm text-destructive">
          {loadError ?? "Couldn't load the script asset."}
        </p>
        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            setLoadError(null)
            setPdf(null)
            void fileQuery.refetch()
            setLoadAttempt((n) => n + 1)
          }}
        >
          Try again
        </Button>
      </div>
    )
  }

  if (!pdf) {
    return (
      <div className="space-y-3 p-6">
        <p className="text-sm text-muted-foreground">Rendering pages…</p>
        <Skeleton className="h-96 w-full" />
      </div>
    )
  }

  return (
    <div className="space-y-6 p-6">
      {Array.from({ length: pdf.numPages }, (_, i) => i + 1).map((pageNumber) => (
        <PdfPage
          key={pageNumber}
          pdf={pdf}
          pageNumber={pageNumber}
          claims={claimsByPage.get(pageNumber) ?? []}
          onPin={onSelectClaim}
        />
      ))}
    </div>
  )
}
