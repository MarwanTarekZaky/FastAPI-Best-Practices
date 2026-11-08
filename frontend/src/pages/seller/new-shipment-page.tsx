import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { useNavigate } from "react-router"
import { z } from "zod"

import { useCreateShipment } from "@/api/queries"
import { FormField } from "@/components/form-field"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { FieldGroup } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"

// The same rules as ShipmentCreate in the API, so mistakes show before sending
const shipmentSchema = z.object({
  content: z.string().min(1, "What's inside the package?"),
  weight: z.number({ error: "Enter the weight" }).gt(0).max(25, "At most 25 kg"),
  destination: z.number({ error: "Enter a zip code" }).int().positive(),
  client_contact_email: z.email("Enter the client's email"),
  // Empty, or a number like +201012345678
  client_contact_phone: z
    .string()
    .regex(/^(\+[1-9]\d{7,14})?$/, "International format, like +201012345678"),
})

type ShipmentValues = z.infer<typeof shipmentSchema>

export function NewShipmentPage() {
  const navigate = useNavigate()
  const createShipment = useCreateShipment()
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ShipmentValues>({ resolver: zodResolver(shipmentSchema) })

  function onSubmit(values: ShipmentValues) {
    createShipment.mutate(
      { ...values, client_contact_phone: values.client_contact_phone || null },
      // Errors, like no partner for this zip code, show as a toast (query-client.ts)
      { onSuccess: (shipment) => navigate(`/seller/shipments/${shipment.id}`) },
    )
  }

  return (
    <>
      <PageHeader
        title="New shipment"
        description="A delivery partner who serves the destination is assigned automatically"
      />
      <Card className="max-w-2xl">
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} noValidate>
            <FieldGroup>
              <FormField id="content" label="Content" error={errors.content}>
                <Input
                  id="content"
                  placeholder="Glass vase"
                  aria-invalid={!!errors.content}
                  {...register("content")}
                />
              </FormField>
              <div className="grid gap-4 sm:grid-cols-2">
                <FormField id="weight" label="Weight (kg)" error={errors.weight}>
                  <Input
                    id="weight"
                    type="number"
                    step="0.1"
                    placeholder="2.5"
                    aria-invalid={!!errors.weight}
                    {...register("weight", { valueAsNumber: true })}
                  />
                </FormField>
                <FormField
                  id="destination"
                  label="Destination zip code"
                  error={errors.destination}
                >
                  <Input
                    id="destination"
                    type="number"
                    placeholder="11001"
                    aria-invalid={!!errors.destination}
                    {...register("destination", { valueAsNumber: true })}
                  />
                </FormField>
              </div>
              <FormField
                id="client_contact_email"
                label="Client email"
                error={errors.client_contact_email}
                description="Gets the tracking link and the delivery code"
              >
                <Input
                  id="client_contact_email"
                  type="email"
                  placeholder="client@example.com"
                  aria-invalid={!!errors.client_contact_email}
                  {...register("client_contact_email")}
                />
              </FormField>
              <FormField
                id="client_contact_phone"
                label="Client phone (optional)"
                error={errors.client_contact_phone}
                description="If set, the delivery code goes by SMS instead"
              >
                <Input
                  id="client_contact_phone"
                  type="tel"
                  placeholder="+201012345678"
                  aria-invalid={!!errors.client_contact_phone}
                  {...register("client_contact_phone")}
                />
              </FormField>
              <Button type="submit" className="self-start" disabled={createShipment.isPending}>
                {createShipment.isPending && <Spinner />}
                Create shipment
              </Button>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </>
  )
}
