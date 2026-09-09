import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { ApiError, createProject } from "@/api/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

// The project_id is this project's primary key in the ledger *and* a path segment in
// /app/projects/:projectId -- a space or a slash breaks routing, so the shape is
// enforced here rather than letting the user find out via a 422.
const ID_PATTERN = /^[a-z0-9][a-z0-9-]*$/

function slugify(title: string): string {
  return title
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")
}

// "us, GB , fr" -> ["us", "gb", "fr"]. Territories reach the claim model as ISO
// alpha-2 jurisdictions (packages/claims/models.py), so normalize rather than
// storing whatever casing/spacing was typed.
function parseCodes(raw: string): string[] {
  return raw
    .split(",")
    .map((code) => code.trim().toLowerCase())
    .filter(Boolean)
}

function humanCreateError(err: unknown): string {
  if (!(err instanceof ApiError)) {
    return "Couldn't reach the server. Check your connection and try again."
  }
  // Mapped by status, never by parsing the backend's wording -- same rule as
  // humanAuthError in AuthProvider, so a reworded server error can't leak through.
  if (err.status === 409) return "A project with that ID already exists. Pick a different ID."
  if (err.status === 403) return "Your role can't create projects. Ask a studio admin."
  if (err.status === 422) return "Something in this form wasn't accepted. Check the dates and numbers."
  return "Couldn't create the project. Try again."
}

function Field({
  htmlFor,
  label,
  hint,
  error,
  optional,
  children,
}: {
  htmlFor: string
  label: string
  hint: string
  error?: string
  optional?: boolean
  children: React.ReactNode
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <Label htmlFor={htmlFor}>{label}</Label>
        {optional && <span className="text-xs text-muted-foreground">Optional</span>}
      </div>
      {children}
      {/* The error replaces the hint rather than stacking under it -- the row keeps
          its height, so validating a field doesn't shove the rest of the form down. */}
      <p
        className={
          error
            ? "text-xs leading-relaxed text-destructive"
            : "text-xs leading-relaxed text-muted-foreground"
        }
      >
        {error ?? hint}
      </p>
    </div>
  )
}

export function NewProjectDialog({
  open,
  onOpenChange,
  existingIds,
  onCreated,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  existingIds: string[]
  onCreated: (projectId: string) => void
}) {
  const [title, setTitle] = useState("")
  const [projectId, setProjectId] = useState("")
  const [studioId, setStudioId] = useState("studio-1")
  const [releaseDate, setReleaseDate] = useState("")
  const [budgetCap, setBudgetCap] = useState("10.00")
  const [territories, setTerritories] = useState("")
  const [countries, setCountries] = useState("")
  const [idTouched, setIdTouched] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: createProject,
    onSuccess: (project) => {
      void queryClient.invalidateQueries({ queryKey: ["projects"] })
      reset()
      onCreated(project.project_id)
    },
  })

  function reset() {
    setTitle("")
    setProjectId("")
    setStudioId("studio-1")
    setReleaseDate("")
    setBudgetCap("10.00")
    setTerritories("")
    setCountries("")
    setIdTouched(false)
    setErrors({})
    mutation.reset()
  }

  function validate(): Record<string, string> {
    const next: Record<string, string> = {}
    if (!title.trim()) next.title = "Give the production a title."
    if (!projectId.trim()) {
      next.projectId = "A project ID is required."
    } else if (!ID_PATTERN.test(projectId.trim())) {
      next.projectId = "Use lowercase letters, numbers and hyphens only — no spaces."
    } else if (existingIds.includes(projectId.trim())) {
      next.projectId = "You already have a project with that ID."
    }
    if (!studioId.trim()) next.studioId = "A studio ID is required."
    const budget = Number(budgetCap)
    if (budgetCap.trim() && (Number.isNaN(budget) || budget <= 0)) {
      next.budgetCap = "Enter an amount greater than 0."
    }
    return next
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const found = validate()
    setErrors(found)
    // Previously an invalid form just `return`ed and the button did nothing at all --
    // a silent dead end. Now every reason it won't submit is stated on the field.
    if (Object.keys(found).length > 0) return

    mutation.mutate({
      project_id: projectId.trim(),
      studio_id: studioId.trim(),
      title: title.trim(),
      release_date: releaseDate || null,
      shooting_countries: parseCodes(countries),
      distribution_territories: parseCodes(territories),
      budget_cap_usd: budgetCap.trim() ? Number(budgetCap) : 10,
    })
  }

  const parsedTerritories = parseCodes(territories)
  const parsedCountries = parseCodes(countries)

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) reset()
        onOpenChange(next)
      }}
    >
      {/* Only the field area scrolls: the title and the Create button stay pinned, so
          a seven-field form can't push its own primary action below the fold. */}
      <DialogContent className="flex max-h-[85vh] flex-col sm:max-w-lg">
        <DialogHeader className="shrink-0">
          <DialogTitle>New project</DialogTitle>
          <DialogDescription>
            A project is one production: its script and cut, every claim Ouroboros
            extracts from them, and the monitors that keep watching those claims after
            they're verified.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col gap-4">
          <div className="-mr-2 min-h-0 flex-1 space-y-5 overflow-y-auto pr-2">
            <div className="space-y-4">
              <Field
                htmlFor="np-title"
                label="Title"
                hint="How your team refers to this production. Shown in the sidebar and page header."
                error={errors.title}
              >
                <Input
                  id="np-title"
                  autoFocus
                  placeholder="The Long Take"
                  value={title}
                  aria-invalid={Boolean(errors.title)}
                  onChange={(e) => {
                    setTitle(e.target.value)
                    if (!idTouched) setProjectId(slugify(e.target.value))
                  }}
                />
              </Field>

              <Field
                htmlFor="np-id"
                label="Project ID"
                hint="Permanent. Used in this project's URL and as its key in the verification ledger — it can't be changed later. Lowercase letters, numbers and hyphens."
                error={errors.projectId}
              >
                <Input
                  id="np-id"
                  className="font-mono"
                  placeholder="the-long-take"
                  value={projectId}
                  aria-invalid={Boolean(errors.projectId)}
                  onChange={(e) => {
                    setIdTouched(true)
                    setProjectId(e.target.value)
                  }}
                />
              </Field>

              <Field
                htmlFor="np-studio"
                label="Studio ID"
                hint="Projects that share a studio ID share prior clearance decisions — Ouroboros reuses what your studio already cleared as precedent instead of re-litigating it."
                error={errors.studioId}
              >
                <Input
                  id="np-studio"
                  className="font-mono"
                  placeholder="studio-1"
                  value={studioId}
                  aria-invalid={Boolean(errors.studioId)}
                  onChange={(e) => setStudioId(e.target.value)}
                />
              </Field>
            </div>

            <div className="space-y-4 border-t border-border pt-5">
              <div>
                <h3 className="text-sm font-medium text-foreground">Production details</h3>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  All optional — but these are what the header metrics and the legal
                  assessment actually read from.
                </p>
              </div>

              <Field
                htmlFor="np-release"
                label="Release date"
                optional
                hint="Drives the “To release” countdown in the project header. Leave blank if the date isn't locked yet — the header just shows a dash."
              >
                <Input
                  id="np-release"
                  type="date"
                  value={releaseDate}
                  onChange={(e) => setReleaseDate(e.target.value)}
                />
              </Field>

              <Field
                htmlFor="np-budget"
                label="Budget cap (USD)"
                optional
                hint="A real cap, not a display value: agent runs stop with a budget error once this project's spend passes it, and warn at 80%."
                error={errors.budgetCap}
              >
                <Input
                  id="np-budget"
                  type="number"
                  step="0.01"
                  min="0"
                  className="font-mono"
                  value={budgetCap}
                  aria-invalid={Boolean(errors.budgetCap)}
                  onChange={(e) => setBudgetCap(e.target.value)}
                />
              </Field>

              <Field
                htmlFor="np-territories"
                label="Distribution territories"
                optional
                hint="Comma-separated ISO country codes. Every claim is assessed against these as its legal jurisdictions, so this changes what counts as risky."
              >
                <Input
                  id="np-territories"
                  className="font-mono"
                  placeholder="us, gb, fr"
                  value={territories}
                  onChange={(e) => setTerritories(e.target.value)}
                />
                {parsedTerritories.length > 0 && (
                  <p className="font-mono text-xs text-muted-foreground">
                    Saves as: {parsedTerritories.join(" · ")}
                  </p>
                )}
              </Field>

              <Field
                htmlFor="np-countries"
                label="Shooting countries"
                optional
                hint="Comma-separated ISO country codes, recorded on the project as production context."
              >
                <Input
                  id="np-countries"
                  className="font-mono"
                  placeholder="us, ie"
                  value={countries}
                  onChange={(e) => setCountries(e.target.value)}
                />
                {parsedCountries.length > 0 && (
                  <p className="font-mono text-xs text-muted-foreground">
                    Saves as: {parsedCountries.join(" · ")}
                  </p>
                )}
              </Field>
            </div>
          </div>

          {mutation.isError && (
            <p className="shrink-0 text-sm text-destructive">{humanCreateError(mutation.error)}</p>
          )}

          <DialogFooter className="shrink-0">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onOpenChange(false)}
              disabled={mutation.isPending}
            >
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={mutation.isPending}>
              {mutation.isPending ? "Creating…" : "Create project"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
