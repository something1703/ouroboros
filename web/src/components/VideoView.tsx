import { useEffect, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { getAssetProxy, getAssetTimeline } from "@/api/client"
import { Skeleton } from "@/components/ui/skeleton"
import type { Segment, TimelineClaim } from "@/api/types"

function verdictColor(verdict: string | null): string {
  if (verdict === "contradicted") return "var(--destructive)"
  if (verdict === "partially_supported") return "var(--brand)"
  return "var(--muted-foreground)" // supported, unverifiable, or not yet verified
}

function formatTime(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${seconds.toString().padStart(2, "0")}`
}

export function VideoView({
  assetId,
  onSelectClaim,
}: {
  assetId: string
  onSelectClaim: (claimId: string) => void
}) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const activeSegmentRef = useRef<HTMLLIElement>(null)
  const [currentMs, setCurrentMs] = useState(0)

  const proxyQuery = useQuery({
    queryKey: ["asset-proxy", assetId],
    queryFn: () => getAssetProxy(assetId),
  })
  const timelineQuery = useQuery({
    queryKey: ["asset-timeline", assetId],
    queryFn: () => getAssetTimeline(assetId),
  })

  useEffect(() => {
    activeSegmentRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" })
  }, [currentMs])

  if (proxyQuery.isLoading || timelineQuery.isLoading) {
    return (
      <div className="space-y-3 p-6">
        <Skeleton className="h-80 w-full" />
      </div>
    )
  }

  if (proxyQuery.isError || timelineQuery.isError) {
    return <p className="p-6 text-sm text-destructive">Couldn't load the video asset.</p>
  }

  const proxy = proxyQuery.data
  const timeline = timelineQuery.data
  const durationMs = timeline?.duration_ms ?? 0
  const claims = (timeline?.claims ?? []).filter(
    (c): c is TimelineClaim & { t_start_ms: number } => c.t_start_ms != null,
  )
  const segments = timeline?.segments ?? []

  if (!proxy?.proxy_url) {
    return (
      <p className="p-6 text-sm text-muted-foreground">
        No proxy video available for this cut yet.
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-4 p-6 lg:flex-row">
      <div className="flex-1 space-y-3">
        <video
          ref={videoRef}
          src={proxy.proxy_url}
          poster={proxy.poster_url ?? undefined}
          controls
          className="w-full rounded-md border border-border bg-black"
          onTimeUpdate={(e) => setCurrentMs(e.currentTarget.currentTime * 1000)}
        />

        {durationMs > 0 && (
          <div
            className="relative h-3 w-full rounded-full bg-muted"
            role="group"
            aria-label="Claim scrubber"
          >
            {claims.map((claim) => (
              <button
                key={claim.claim_id}
                type="button"
                title={claim.claim_text}
                onClick={() => {
                  if (videoRef.current) videoRef.current.currentTime = claim.t_start_ms / 1000
                  onSelectClaim(claim.claim_id)
                }}
                className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-card transition-transform hover:scale-125"
                style={{
                  left: `${(claim.t_start_ms / durationMs) * 100}%`,
                  backgroundColor: verdictColor(claim.verdict),
                }}
              />
            ))}
          </div>
        )}
      </div>

      <div className="w-full space-y-1 overflow-y-auto lg:w-80" style={{ maxHeight: "24rem" }}>
        <p className="mb-2 text-xs font-medium text-muted-foreground">Transcript</p>
        <ul>
          {segments.map((segment: Segment) => {
            const active = currentMs >= segment.t_start_ms && currentMs <= segment.t_end_ms
            return (
              <li
                key={`${segment.t_start_ms}-${segment.t_end_ms}`}
                ref={active ? activeSegmentRef : undefined}
                className={
                  active
                    ? "rounded-md bg-accent px-2 py-1.5 text-sm text-foreground"
                    : "px-2 py-1.5 text-sm text-muted-foreground"
                }
              >
                <span className="font-mono text-xs">{formatTime(segment.t_start_ms)}</span>
                {segment.speaker && <span className="ml-1.5 font-medium">{segment.speaker}:</span>}{" "}
                {segment.transcript}
              </li>
            )
          })}
        </ul>
      </div>
    </div>
  )
}
