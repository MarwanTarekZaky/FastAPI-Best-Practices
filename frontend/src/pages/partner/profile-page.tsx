import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { usePartnerProfile, useUpdatePartner } from "@/api/queries"
import { FormField } from "@/components/form-field"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { FieldGroup } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { parseZipCodes, ZIP_CODE_LIST } from "@/lib/format"

const profileSchema = z.object({
  serviceable_zip_codes: z
    .string()
    .regex(ZIP_CODE_LIST, "Zip codes separated by commas, like 11001, 11002"),
  max_handling_capacity: z.number({ error: "Enter a number" }).int().min(1),
})

type ProfileValues = z.infer<typeof profileSchema>

export function PartnerProfilePage() {
  const profile = usePartnerProfile()
  const updatePartner = useUpdatePartner()

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    // `values` fills the form when the profile arrives from the API
    values: profile.data && {
      serviceable_zip_codes: profile.data.serviceable_zip_codes.join(", "),
      max_handling_capacity: profile.data.max_handling_capacity,
    },
  })

  function onSubmit(values: ProfileValues) {
    updatePartner.mutate({
      serviceable_zip_codes: parseZipCodes(values.serviceable_zip_codes),
      max_handling_capacity: values.max_handling_capacity,
    })
  }

  return (
    <>
      <PageHeader title="Profile" description="Where you deliver and how much you can carry" />
      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>{profile.data?.name ?? <Skeleton className="h-5 w-40" />}</CardTitle>
          <CardDescription>{profile.data?.email}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} noValidate>
            <FieldGroup>
              <FormField
                id="serviceable_zip_codes"
                label="Zip codes you deliver to"
                error={errors.serviceable_zip_codes}
                description="New shipments to these zip codes can be assigned to you"
              >
                <Input
                  id="serviceable_zip_codes"
                  aria-invalid={!!errors.serviceable_zip_codes}
                  {...register("serviceable_zip_codes")}
                />
              </FormField>
              <FormField
                id="max_handling_capacity"
                label="Shipments you can handle at once"
                error={errors.max_handling_capacity}
              >
                <Input
                  id="max_handling_capacity"
                  type="number"
                  aria-invalid={!!errors.max_handling_capacity}
                  {...register("max_handling_capacity", { valueAsNumber: true })}
                />
              </FormField>
              <Button
                type="submit"
                className="self-start"
                disabled={updatePartner.isPending || !profile.data}
              >
                {updatePartner.isPending && <Spinner />}
                Save
              </Button>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </>
  )
}
