import { zodResolver } from "@hookform/resolvers/zod"
import { REGEXP_ONLY_DIGITS } from "input-otp"
import { ScanQrCodeIcon } from "lucide-react"
import { lazy, Suspense, useState } from "react"
import { Controller, useForm } from "react-hook-form"
import { useParams } from "react-router"
import { z } from "zod"

import type { ShipmentRead } from "@/api/generated"
import {
  useResendCode,
  useShipment,
  useUpdateShipment,
  useVerifyDelivery,
} from "@/api/queries"
import { FormField } from "@/components/form-field"
import { PageHeader } from "@/components/page-header"
import { ShipmentDetails } from "@/components/shipment-details"
import { ShipmentTimeline } from "@/components/shipment-timeline"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { FieldError, FieldGroup } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { InputOTP, InputOTPGroup, InputOTPSlot } from "@/components/ui/input-otp"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { isFinished, STATUS_LABELS } from "@/lib/format"

// The scanner library is big and only needed here, so it's downloaded
// the first time someone opens the scanner (code splitting)
const QrScannerDialog = lazy(() =>
  import("@/components/qr-scanner-dialog").then((module) => ({
    default: module.QrScannerDialog,
  })),
)

export function PartnerShipmentPage() {
  const { id = "" } = useParams()
  const { data: shipment, isPending, isError } = useShipment(id)

  if (isPending) {
    return <Skeleton className="h-96 w-full" />
  }
  if (isError) {
    return <p className="text-muted-foreground">This shipment couldn't be loaded.</p>
  }

  return (
    <>
      <PageHeader title="Delivery" description="Update the client on every step" />
      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <div className="flex flex-col gap-6">
          <ShipmentDetails shipment={shipment} />
          {shipment.status === "out_for_delivery" && <DeliveryCard id={shipment.id} />}
          {!isFinished(shipment.status) && <UpdateCard shipment={shipment} />}
        </div>
        <ShipmentTimeline events={shipment.timeline} />
      </div>
    </>
  )
}

// "delivered" needs the client's code, so it's not in this list
const PARTNER_STATUSES = ["in_transit", "out_for_delivery"] as const

const updateSchema = z
  .object({
    status: z.enum(PARTNER_STATUSES).optional(),
    location: z.number().int().positive().optional(),
    description: z.string(),
    estimated_delivery: z.string(),
  })
  .refine(
    (values) =>
      values.status || values.location || values.description || values.estimated_delivery,
    { message: "Change at least one field", path: ["root"] },
  )

type UpdateValues = z.infer<typeof updateSchema>

function UpdateCard({ shipment }: { shipment: ShipmentRead }) {
  const updateShipment = useUpdateShipment(shipment.id)
  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<UpdateValues>({
    resolver: zodResolver(updateSchema),
    defaultValues: { description: "", estimated_delivery: "" },
  })

  function onSubmit(values: UpdateValues) {
    updateShipment.mutate(
      {
        status: values.status,
        location: values.location,
        description: values.description || undefined,
        // datetime-local gives local time without a timezone, the API needs one
        estimated_delivery: values.estimated_delivery
          ? new Date(values.estimated_delivery).toISOString()
          : undefined,
      },
      { onSuccess: () => reset() },
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Update progress</CardTitle>
        <CardDescription>The client gets an email when the status changes</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} noValidate>
          <FieldGroup>
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField id="status" label="Status" error={errors.status}>
                {/* Select isn't a normal <input>, Controller connects it to the form */}
                <Controller
                  control={control}
                  name="status"
                  render={({ field }) => (
                    <Select value={field.value ?? ""} onValueChange={field.onChange}>
                      <SelectTrigger id="status" className="w-full">
                        <SelectValue placeholder="No change" />
                      </SelectTrigger>
                      <SelectContent>
                        {PARTNER_STATUSES.map((status) => (
                          <SelectItem key={status} value={status}>
                            {STATUS_LABELS[status]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </FormField>
              <FormField id="location" label="Current zip code" error={errors.location}>
                <Input
                  id="location"
                  type="number"
                  placeholder="11002"
                  {...register("location", {
                    // Empty means "no change", not 0 or NaN
                    setValueAs: (value) => (value === "" ? undefined : Number(value)),
                  })}
                />
              </FormField>
            </div>
            <FormField id="description" label="Note (optional)">
              <Textarea
                id="description"
                placeholder="Arrived at the hub"
                {...register("description")}
              />
            </FormField>
            <FormField id="estimated_delivery" label="New estimated delivery (optional)">
              <Input
                id="estimated_delivery"
                type="datetime-local"
                {...register("estimated_delivery")}
              />
            </FormField>
            <FieldError errors={[errors.root]} />
            <Button type="submit" className="self-start" disabled={updateShipment.isPending}>
              {updateShipment.isPending && <Spinner />}
              Save update
            </Button>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  )
}

function DeliveryCard({ id }: { id: string }) {
  const [code, setCode] = useState("")
  const [scanning, setScanning] = useState(false)
  const verify = useVerifyDelivery(id)
  const resend = useResendCode(id)

  function confirm(value: string) {
    verify.mutate(value, { onError: () => setCode("") })
  }

  return (
    <Card className="border-amber-300">
      <CardHeader>
        <CardTitle>Confirm delivery</CardTitle>
        <CardDescription>
          Ask the client for the 6 digit code from their email or SMS, or scan the QR
          code in their email.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <InputOTP
          maxLength={6}
          pattern={REGEXP_ONLY_DIGITS}
          value={code}
          onChange={setCode}
          aria-label="Delivery code"
        >
          <InputOTPGroup>
            {[0, 1, 2, 3, 4, 5].map((index) => (
              <InputOTPSlot key={index} index={index} />
            ))}
          </InputOTPGroup>
        </InputOTP>
        <div className="flex flex-wrap gap-2">
          <Button disabled={code.length !== 6 || verify.isPending} onClick={() => confirm(code)}>
            {verify.isPending && <Spinner />}
            Confirm delivery
          </Button>
          <Button variant="outline" onClick={() => setScanning(true)}>
            <ScanQrCodeIcon />
            Scan QR code
          </Button>
          <Button variant="ghost" disabled={resend.isPending} onClick={() => resend.mutate()}>
            Send a new code
          </Button>
        </div>
      </CardContent>
      {scanning && (
        <Suspense fallback={null}>
          <QrScannerDialog
            open
            onOpenChange={setScanning}
            onCode={(scanned) => {
              setScanning(false)
              setCode(scanned)
              confirm(scanned)
            }}
          />
        </Suspense>
      )}
    </Card>
  )
}
