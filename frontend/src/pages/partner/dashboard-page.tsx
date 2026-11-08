import { CircleCheckIcon, GaugeIcon, PackageIcon, TruckIcon } from "lucide-react"
import { useState } from "react"

import { useMyShipments, usePartnerProfile } from "@/api/queries"
import { PageHeader } from "@/components/page-header"
import { ShipmentsTable } from "@/components/shipments-table"
import { StatCard } from "@/components/stat-card"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { isFinished } from "@/lib/format"

export function PartnerDashboardPage() {
  const [tab, setTab] = useState<"active" | "finished">("active")
  const shipments = useMyShipments("partner")
  const profile = usePartnerProfile()

  const all = shipments.data ?? []
  const active = all.filter((shipment) => !isFinished(shipment.status))
  const finished = all.filter((shipment) => isFinished(shipment.status))
  const delivered = finished.filter((shipment) => shipment.status === "delivered")
  const visible = tab === "active" ? active : finished

  return (
    <>
      <PageHeader
        title="Deliveries"
        description="Shipments assigned to you, update them as you go"
      />

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <StatCard title="Active" value={active.length} icon={<TruckIcon />} />
        <StatCard
          title="Capacity used"
          value={`${active.length} / ${profile.data?.max_handling_capacity ?? "-"}`}
          icon={<GaugeIcon />}
        />
        <StatCard title="Delivered" value={delivered.length} icon={<CircleCheckIcon />} />
      </div>

      <Card>
        <CardHeader>
          <Tabs value={tab} onValueChange={(value) => setTab(value as typeof tab)}>
            <TabsList>
              <TabsTrigger value="active">Active ({active.length})</TabsTrigger>
              <TabsTrigger value="finished">Finished ({finished.length})</TabsTrigger>
            </TabsList>
          </Tabs>
        </CardHeader>
        <CardContent>
          {shipments.isPending ? (
            <Skeleton className="h-32 w-full" />
          ) : visible.length === 0 ? (
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <PackageIcon />
                </EmptyMedia>
                <EmptyTitle>Nothing here</EmptyTitle>
                <EmptyDescription>
                  New shipments to your zip codes show up here automatically.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <ShipmentsTable shipments={visible} basePath="/partner/shipments" />
          )}
        </CardContent>
      </Card>
    </>
  )
}
