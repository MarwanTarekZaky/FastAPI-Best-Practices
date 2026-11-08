import { Link } from "react-router"

import type { ShipmentRead } from "@/api/generated"
import { StatusBadge } from "@/components/status-badge"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatDate, formatTagName } from "@/lib/format"

export function ShipmentsTable({
  shipments,
  basePath,
}: {
  shipments: ShipmentRead[]
  // Each row links to `${basePath}/${shipment.id}`
  basePath: string
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Content</TableHead>
          <TableHead>Status</TableHead>
          {/* Hidden on small screens, so the table fits on a phone */}
          <TableHead className="hidden md:table-cell">Destination</TableHead>
          <TableHead className="hidden lg:table-cell">Tags</TableHead>
          <TableHead className="hidden sm:table-cell">Estimated delivery</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {shipments.map((shipment) => (
          <TableRow key={shipment.id}>
            <TableCell className="font-medium">
              <Link to={`${basePath}/${shipment.id}`} className="hover:underline">
                {shipment.content}
              </Link>
            </TableCell>
            <TableCell>
              <StatusBadge status={shipment.status} />
            </TableCell>
            <TableCell className="hidden md:table-cell">{shipment.destination}</TableCell>
            <TableCell className="hidden lg:table-cell">
              <div className="flex flex-wrap gap-1">
                {shipment.tags.map((tag) => (
                  <Badge key={tag.name} variant="outline">
                    {formatTagName(tag.name)}
                  </Badge>
                ))}
              </div>
            </TableCell>
            <TableCell className="hidden sm:table-cell">
              {formatDate(shipment.estimated_delivery)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
