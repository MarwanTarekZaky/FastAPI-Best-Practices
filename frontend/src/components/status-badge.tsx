import type { ShipmentStatus } from "@/api/generated"
import { Badge } from "@/components/ui/badge"
import { STATUS_LABELS } from "@/lib/format"

const COLORS: Record<ShipmentStatus, string> = {
  placed: "bg-slate-100 text-slate-700",
  in_transit: "bg-blue-100 text-blue-700",
  out_for_delivery: "bg-amber-100 text-amber-800",
  delivered: "bg-green-100 text-green-700",
  cancelled: "bg-red-100 text-red-700",
}

export function StatusBadge({ status }: { status: ShipmentStatus | null }) {
  if (!status) {
    return <Badge variant="outline">Unknown</Badge>
  }
  return <Badge className={COLORS[status]}>{STATUS_LABELS[status]}</Badge>
}
