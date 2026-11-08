import { PackageSearchIcon } from "lucide-react"
import { Link, useParams } from "react-router"

import { useShipment } from "@/api/queries"
import { Logo } from "@/components/logo"
import { ShipmentDetails } from "@/components/shipment-details"
import { ShipmentTimeline } from "@/components/shipment-timeline"
import { Button } from "@/components/ui/button"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"

// Public page: the client opens it from the tracking link, no login needed
export function TrackPage() {
  // The :id part of the URL /track/:id
  const { id = "" } = useParams()
  // This page shows its own message instead of a toast
  const { data: shipment, isPending, isError } = useShipment(id, false)

  return (
    <div className="flex min-h-svh flex-col bg-muted">
      <header className="p-4 md:px-10">
        <Logo />
      </header>
      <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 p-4 md:p-6">
        {isPending && <Skeleton className="h-64 w-full" />}

        {isError && (
          <Empty className="bg-background">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <PackageSearchIcon />
              </EmptyMedia>
              <EmptyTitle>Shipment not found</EmptyTitle>
              <EmptyDescription>Check the tracking id and try again.</EmptyDescription>
            </EmptyHeader>
            <EmptyContent>
              <Button variant="outline" asChild>
                <Link to="/">Back home</Link>
              </Button>
            </EmptyContent>
          </Empty>
        )}

        {shipment && (
          <>
            <ShipmentDetails shipment={shipment} />
            <ShipmentTimeline events={shipment.timeline} />
          </>
        )}
      </main>
    </div>
  )
}
