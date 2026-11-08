import type { ShipmentEvent } from "@/api/generated"
import { StatusBadge } from "@/components/status-badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { formatDate } from "@/lib/format"

export function ShipmentTimeline({ events }: { events: ShipmentEvent[] }) {
  // The API sends the oldest event first, the newest goes on top here.
  // A copy, because reverse() changes the array it's called on
  const newestFirst = [...events].reverse()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Timeline</CardTitle>
      </CardHeader>
      <CardContent>
        <ol className="flex flex-col gap-6 border-l pl-6">
          {newestFirst.map((event) => (
            <li key={event.id} className="relative">
              <span className="absolute top-1.5 -left-[30.5px] size-3 rounded-full bg-primary ring-4 ring-card" />
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge status={event.status} />
                <span className="text-sm text-muted-foreground">
                  {formatDate(event.created_at)}
                </span>
              </div>
              <p className="mt-1 text-sm">{event.description}</p>
              <p className="text-xs text-muted-foreground">Zip code {event.location}</p>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  )
}
