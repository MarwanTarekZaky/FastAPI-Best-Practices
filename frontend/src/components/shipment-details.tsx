import type { ShipmentRead } from "@/api/generated"
import { StatusBadge } from "@/components/status-badge"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { formatDate, formatTagName } from "@/lib/format"

export function ShipmentDetails({
  shipment,
  showTags = true,
}: {
  shipment: ShipmentRead
  showTags?: boolean
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">{shipment.content}</CardTitle>
        <CardDescription className="font-mono text-xs break-all">
          {shipment.id}
        </CardDescription>
        <CardAction>
          <StatusBadge status={shipment.status} />
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
          <Detail label="Weight" value={`${shipment.weight} kg`} />
          <Detail label="Destination" value={`Zip code ${shipment.destination}`} />
          <Detail
            label="Estimated delivery"
            value={formatDate(shipment.estimated_delivery)}
          />
        </dl>

        {showTags && shipment.tags.length > 0 && (
          <div className="flex flex-col gap-2">
            <h3 className="text-sm font-medium">Handling instructions</h3>
            <ul className="flex flex-col gap-1 text-sm">
              {shipment.tags.map((tag) => (
                <li key={tag.name}>
                  <span className="font-medium">{formatTagName(tag.name)}:</span>{" "}
                  {tag.instruction}
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  )
}
