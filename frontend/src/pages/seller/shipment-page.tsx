import { CopyIcon, XIcon } from "lucide-react"
import { useState } from "react"
import { useParams } from "react-router"
import { toast } from "sonner"

import type { ShipmentRead, TagName } from "@/api/generated"
import {
  useAddTag,
  useCancelShipment,
  useRemoveTag,
  useShipment,
  useTags,
} from "@/api/queries"
import { PageHeader } from "@/components/page-header"
import { ShipmentDetails } from "@/components/shipment-details"
import { ShipmentTimeline } from "@/components/shipment-timeline"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { formatTagName, isFinished } from "@/lib/format"

export function SellerShipmentPage() {
  const { id = "" } = useParams()
  const { data: shipment, isPending, isError } = useShipment(id)

  if (isPending) {
    return <Skeleton className="h-96 w-full" />
  }
  if (isError) {
    return <p className="text-muted-foreground">This shipment couldn't be loaded.</p>
  }

  function copyTrackingLink() {
    // The client's public page, the same one the home page opens
    navigator.clipboard.writeText(`${window.location.origin}/track/${id}`)
    toast.success("Tracking link copied")
  }

  return (
    <>
      <PageHeader title="Shipment" description="Details, tags and the delivery timeline">
        <Button variant="outline" onClick={copyTrackingLink}>
          <CopyIcon />
          Copy tracking link
        </Button>
        <CancelButton shipment={shipment} />
      </PageHeader>
      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <div className="flex flex-col gap-6">
          <ShipmentDetails shipment={shipment} showTags={false} />
          <TagsCard shipment={shipment} />
        </div>
        <ShipmentTimeline events={shipment.timeline} />
      </div>
    </>
  )
}

function CancelButton({ shipment }: { shipment: ShipmentRead }) {
  const cancel = useCancelShipment(shipment.id)

  return (
    // Asks "are you sure?" first, because cancelling can't be undone
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="destructive" disabled={isFinished(shipment.status)}>
          Cancel shipment
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Cancel this shipment?</AlertDialogTitle>
          <AlertDialogDescription>
            The client gets an email, and the shipment can't be changed after this.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Keep it</AlertDialogCancel>
          <AlertDialogAction variant="destructive" onClick={() => cancel.mutate()}>
            Cancel shipment
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

function TagsCard({ shipment }: { shipment: ShipmentRead }) {
  const [selected, setSelected] = useState<TagName | "">("")
  const tags = useTags()
  const addTag = useAddTag(shipment.id)
  const removeTag = useRemoveTag(shipment.id)

  const locked = isFinished(shipment.status)
  const current = shipment.tags.map((tag) => tag.name)
  const available = (tags.data ?? []).filter((tag) => !current.includes(tag.name))

  return (
    <Card>
      <CardHeader>
        <CardTitle>Tags</CardTitle>
        <CardDescription>Tell the delivery partner how to handle the package</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap gap-2">
          {shipment.tags.length === 0 && (
            <span className="text-sm text-muted-foreground">No tags yet</span>
          )}
          {shipment.tags.map((tag) => (
            <Badge key={tag.name} variant="secondary" title={tag.instruction}>
              {formatTagName(tag.name)}
              {!locked && (
                <button
                  type="button"
                  aria-label={`Remove ${formatTagName(tag.name)}`}
                  className="ml-1 rounded-full hover:text-destructive"
                  onClick={() => removeTag.mutate(tag.name)}
                >
                  <XIcon className="size-3" />
                </button>
              )}
            </Badge>
          ))}
        </div>
        {!locked && (
          <div className="flex gap-2">
            <Select value={selected} onValueChange={(value) => setSelected(value as TagName)}>
              <SelectTrigger className="w-56" aria-label="Tag to add">
                <SelectValue placeholder="Choose a tag" />
              </SelectTrigger>
              <SelectContent>
                {available.map((tag) => (
                  <SelectItem key={tag.name} value={tag.name}>
                    {formatTagName(tag.name)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              disabled={!selected || addTag.isPending}
              onClick={() => {
                if (selected) {
                  addTag.mutate(selected, { onSuccess: () => setSelected("") })
                }
              }}
            >
              Add tag
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
