import { useState } from "react"
import { useInfiniteQuery } from "@tanstack/react-query"
import { getEvents } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import type { EventEntry, EventKind } from "@/api/types"

const KIND_LABELS: Record<EventKind, string> = {
  monitor_event: "Monitor detected",
  reverified: "Re-verified",
  risk_changed: "Risk changed",
}

const KIND_FILTERS: (EventKind | "all")[] = ["all", "monitor_event", "reverified", "risk_changed"]

// Unset until the real hackathon submission happens (docs/DECISIONS.md) -- with no
// value, the divider simply never renders rather than showing a fabricated date.
const SUBMISSION_AT = import.meta.env.VITE_SUBMISSION_AT as string | undefined

function formatDelta(delta: Record<string, Record<string, unknown>> | undefined): string | null {
  if (!delta || Object.keys(delta).length === 0) return null
  return Object.entries(delta)
    .map(([field, change]) => `${field}: ${String(change.from)} → ${String(change.to)}`)
    .join(", ")
}

export function FeedView({
  projectId,
  onSelectClaim,
}: {
  projectId: string
  onSelectClaim: (claimId: string) => void
}) {
  const [filter, setFilter] = useState<EventKind | "all">("all")

  const query = useInfiniteQuery({
    queryKey: ["events", projectId],
    queryFn: ({ pageParam }: { pageParam: string | undefined }) => getEvents(projectId, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_before ?? undefined,
  })

  const events = query.data?.pages.flatMap((page) => page.events) ?? []
  const filtered = filter === "all" ? events : events.filter((e) => e.kind === filter)
  const submissionAt = SUBMISSION_AT ? Date.parse(SUBMISSION_AT) : null

  if (query.isLoading) {
    return (
      <div className="space-y-2 p-6">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  if (query.isError) {
    return <p className="p-6 text-sm text-destructive">Couldn't load the event feed.</p>
  }

  return (
    <div className="space-y-4 p-6">
      <div className="flex flex-wrap gap-1.5">
        {KIND_FILTERS.map((kind) => (
          <Button
            key={kind}
            size="xs"
            variant={filter === kind ? "secondary" : "outline"}
            onClick={() => setFilter(kind)}
          >
            {kind === "all" ? "All" : KIND_LABELS[kind]}
          </Button>
        ))}
      </div>

      {filtered.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {events.length === 0
            ? "No events yet."
            : `No “${filter === "all" ? "all" : KIND_LABELS[filter]}” events yet.`}
        </p>
      )}

      <ul className="space-y-0.5">
        {filtered.map((event, i) => {
          const at = Date.parse(event.at)
          const previous = filtered[i - 1]
          const showDivider =
            submissionAt != null &&
            at >= submissionAt &&
            (previous == null || Date.parse(previous.at) < submissionAt)
          return (
            <li key={`${event.claim_id ?? "event"}-${event.at}-${i}`}>
              {showDivider && (
                <div className="my-3 flex items-center gap-2 text-xs text-muted-foreground">
                  <div className="h-px flex-1 bg-border" />
                  since submission
                  <div className="h-px flex-1 bg-border" />
                </div>
              )}
              <EventRow event={event} onSelectClaim={onSelectClaim} />
            </li>
          )
        })}
      </ul>

      {query.hasNextPage && (
        <Button
          size="sm"
          variant="outline"
          disabled={query.isFetchingNextPage}
          onClick={() => void query.fetchNextPage()}
        >
          Load more
        </Button>
      )}
    </div>
  )
}

function EventRow({
  event,
  onSelectClaim,
}: {
  event: EventEntry
  onSelectClaim: (claimId: string) => void
}) {
  const delta = formatDelta(event.delta)
  const content = (
    <div className="flex items-start gap-3 border-b border-border py-2.5 last:border-0">
      <span className="shrink-0 font-mono text-xs text-muted-foreground">
        {new Date(event.at).toLocaleString()}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm text-foreground">
          {event.kind ? KIND_LABELS[event.kind] : "Event"}
          {event.summary ? `: ${event.summary}` : ""}
        </p>
        {delta && <p className="text-xs text-muted-foreground">{delta}</p>}
      </div>
    </div>
  )

  if (!event.claim_id) return content

  return (
    <button
      type="button"
      onClick={() => onSelectClaim(event.claim_id!)}
      className="w-full text-left transition-colors hover:bg-accent"
    >
      {content}
    </button>
  )
}
