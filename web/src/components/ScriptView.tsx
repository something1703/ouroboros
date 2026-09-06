import { useEffect, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import * as pdfjsLib from "pdfjs-dist"
import type { PDFDocumentProxy } from "pdfjs-dist"
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url"
import { getAssetFile, getAssetTimeline } from "@/api/client"
import { Skeleton } from "@/components/ui/skeleton"
import type { RiskLevel, TimelineClaim } from "@/api/types"

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl

const RISK_RANK: Record<RiskLevel, number> = { blocking: 0, high: 1, medium: 2, low: 3, none: 4 }

function riskColor(level: RiskLevel | null): string {
  if (level === "blocking" || level === "high") return "var(--destructive)"
  if (level === "medium") return "var(--brand)"
  return "var(--border)"
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

  return (
    <div className="flex gap-3">
      <div
        className="w-1 shrink-0 rounded-full"
        style={{ backgroundColor: riskColor(pageRisk(claims)) }}
        aria-hidden
      />
      <div className="flex-1">
        <canvas ref={canvasRef} className="max-w-full rounded-md border border-border" />
      </div>
      <div className="w-48 shrink-0 space-y-1.5 pt-1">
        <p className="font-mono text-xs text-muted-foreground">Page {pageNumber}</p>
        {claims.map((claim) => (
          <button
            key={claim.claim_id}
            type="button"
            onClick={() => onPin(claim.claim_id)}
            className="flex w-full items-start gap-1.5 rounded-md px-1.5 py-1 text-left text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            <span
              className="mt-1 size-1.5 shrink-0 rounded-full"
              style={{ backgroundColor: riskColor(claim.risk_level) }}
              aria-hidden
            />
            <span className="truncate">{claim.claim_text}</span>
          </button>
        ))}
      </div>
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

  const fileQuery = useQuery({
    queryKey: ["asset-file", assetId],
    queryFn: () => getAssetFile(assetId),
  })
  const timelineQuery = useQuery({
    queryKey: ["asset-timeline", assetId],
    queryFn: () => getAssetTimeline(assetId),
  })

  useEffect(() => {
    if (!fileQuery.data) return
    let cancelled = false
    void pdfjsLib
      .getDocument({ url: fileQuery.data.url })
      .promise.then((doc) => {
        if (!cancelled) setPdf(doc)
      })
      .catch((err: unknown) => {
        if (!cancelled) setLoadError(err instanceof Error ? err.message : "Couldn't load script")
      })
    return () => {
      cancelled = true
    }
  }, [fileQuery.data])

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
        <Skeleton className="h-96 w-full" />
      </div>
    )
  }

  if (fileQuery.isError || loadError) {
    return (
      <p className="p-6 text-sm text-destructive">
        {loadError ?? "Couldn't load the script asset."}
      </p>
    )
  }

  if (!pdf) {
    return (
      <div className="space-y-3 p-6">
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
