import {
  CircleCheckIcon,
  CircleXIcon,
  PackageIcon,
  PackagePlusIcon,
  TruckIcon,
} from "lucide-react"
import { useState } from "react"
import { Link } from "react-router"

import type { ShipmentRead, TagName } from "@/api/generated"
import { useMyShipments, useTags, useTagShipments } from "@/api/queries"
import { PageHeader } from "@/components/page-header"
import { ShipmentsTable } from "@/components/shipments-table"
import { StatCard } from "@/components/stat-card"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { formatTagName, isFinished } from "@/lib/format"

const FILTERS = {
  all: () => true,
  active: (shipment: ShipmentRead) => !isFinished(shipment.status),
  delivered: (shipment: ShipmentRead) => shipment.status === "delivered",
  cancelled: (shipment: ShipmentRead) => shipment.status === "cancelled",
}
type Filter = keyof typeof FILTERS

export function SellerDashboardPage() {
  const [filter, setFilter] = useState<Filter>("all")
  const [tag, setTag] = useState<TagName | null>(null)

  const shipments = useMyShipments("seller")
  const tagShipments = useTagShipments(tag)
  const tags = useTags()

  const all = shipments.data ?? []
  // With a tag chosen, the list comes from GET /tag/shipments instead
  const list = tag ? tagShipments : shipments
  const visible = (list.data ?? []).filter(FILTERS[filter])

  return (
    <>
      <PageHeader title="Shipments" description="Everything you've sent with FastShip">
        <Button asChild>
          <Link to="/seller/shipments/new">
            <PackagePlusIcon />
            New shipment
          </Link>
        </Button>
      </PageHeader>

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard title="Total" value={all.length} icon={<PackageIcon />} />
        <StatCard
          title="Active"
          value={all.filter(FILTERS.active).length}
          icon={<TruckIcon />}
        />
        <StatCard
          title="Delivered"
          value={all.filter(FILTERS.delivered).length}
          icon={<CircleCheckIcon />}
        />
        <StatCard
          title="Cancelled"
          value={all.filter(FILTERS.cancelled).length}
          icon={<CircleXIcon />}
        />
      </div>

      <Card>
        <CardHeader className="flex flex-wrap items-center justify-between gap-4">
          <Tabs value={filter} onValueChange={(value) => setFilter(value as Filter)}>
            <TabsList>
              <TabsTrigger value="all">All</TabsTrigger>
              <TabsTrigger value="active">Active</TabsTrigger>
              <TabsTrigger value="delivered">Delivered</TabsTrigger>
              <TabsTrigger value="cancelled">Cancelled</TabsTrigger>
            </TabsList>
          </Tabs>
          <Select
            value={tag ?? "any"}
            onValueChange={(value) => setTag(value === "any" ? null : (value as TagName))}
          >
            <SelectTrigger className="w-48" aria-label="Filter by tag">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="any">Any tag</SelectItem>
              {tags.data?.map((tag) => (
                <SelectItem key={tag.name} value={tag.name}>
                  {formatTagName(tag.name)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardHeader>
        <CardContent>
          {list.isPending ? (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : visible.length === 0 ? (
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <PackageIcon />
                </EmptyMedia>
                <EmptyTitle>No shipments here</EmptyTitle>
                <EmptyDescription>
                  {all.length === 0
                    ? "Create your first shipment to see it here."
                    : "No shipment matches these filters."}
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <ShipmentsTable shipments={visible} basePath="/seller/shipments" />
          )}
        </CardContent>
      </Card>
    </>
  )
}
