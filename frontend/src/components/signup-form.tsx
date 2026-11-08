import { zodResolver } from "@hookform/resolvers/zod"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { Link, useNavigate } from "react-router"
import { toast } from "sonner"
import { z } from "zod"

import { api } from "@/api/client"
import { getErrorMessage } from "@/api/errors"
import { useAuth } from "@/auth/auth-context"
import type { Role } from "@/auth/session"
import { FormField } from "@/components/form-field"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Field, FieldDescription, FieldError, FieldGroup } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { parseZipCodes, ZIP_CODE_LIST } from "@/lib/format"

// Both roles need a name, email and password, then each adds its own fields
const accountSchema = z.object({
  name: z.string().min(1, "Enter your name"),
  email: z.email("Enter a valid email"),
  password: z.string().min(8, "At least 8 characters"),
})

const sellerSchema = accountSchema.extend({
  // valueAsNumber turns an empty input into NaN, this message covers it too
  zip_code: z.number({ error: "Enter a zip code" }).int().positive(),
  address: z.string(),
})

const partnerSchema = accountSchema.extend({
  serviceable_zip_codes: z
    .string()
    .regex(ZIP_CODE_LIST, "Zip codes separated by commas, like 11001, 11002"),
  max_handling_capacity: z.number({ error: "Enter a number" }).int().min(1),
})

type SellerValues = z.infer<typeof sellerSchema>
type PartnerValues = z.infer<typeof partnerSchema>

export function SignupForm() {
  const [role, setRole] = useState<Role>("seller")

  return (
    <Card>
      <CardHeader className="text-center">
        <CardTitle className="text-xl">Create your account</CardTitle>
        <CardDescription>Sellers send shipments, partners deliver them</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <Tabs value={role} onValueChange={(value) => setRole(value as Role)}>
          <TabsList className="w-full">
            <TabsTrigger value="seller">Seller</TabsTrigger>
            <TabsTrigger value="partner">Delivery partner</TabsTrigger>
          </TabsList>
        </Tabs>
        {/* Each role has its own form, with its own fields and rules */}
        {role === "seller" ? <SellerSignup /> : <PartnerSignup />}
        <FieldDescription className="text-center">
          Already have an account? <Link to={`/login?role=${role}`}>Log in</Link>
        </FieldDescription>
      </CardContent>
    </Card>
  )
}

// After signing up, log in with the same email and password
function useLoginAfterSignup(role: Role) {
  const { login } = useAuth()
  const navigate = useNavigate()

  return async (email: string, password: string) => {
    await login(role, email, password)
    toast.success("Welcome to FastShip!")
    navigate(`/${role}`, { replace: true })
  }
}

function SellerSignup() {
  const loginAfterSignup = useLoginAfterSignup("seller")
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<SellerValues>({ resolver: zodResolver(sellerSchema) })

  async function onSubmit(values: SellerValues) {
    try {
      await api.seller.registerSeller({ ...values, address: values.address || null })
      await loginAfterSignup(values.email, values.password)
    } catch (error) {
      setError("root", { message: getErrorMessage(error) })
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      <FieldGroup>
        <FormField id="name" label="Business name" error={errors.name}>
          <Input id="name" aria-invalid={!!errors.name} {...register("name")} />
        </FormField>
        <FormField id="email" label="Email" error={errors.email}>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            aria-invalid={!!errors.email}
            {...register("email")}
          />
        </FormField>
        <FormField id="password" label="Password" error={errors.password}>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            aria-invalid={!!errors.password}
            {...register("password")}
          />
        </FormField>
        <FormField
          id="zip_code"
          label="Zip code"
          error={errors.zip_code}
          description="Your shipments start from here"
        >
          <Input
            id="zip_code"
            type="number"
            placeholder="11001"
            aria-invalid={!!errors.zip_code}
            {...register("zip_code", { valueAsNumber: true })}
          />
        </FormField>
        <FormField id="address" label="Address (optional)">
          <Input id="address" {...register("address")} />
        </FormField>
        <SubmitButton isSubmitting={isSubmitting} error={errors.root} />
      </FieldGroup>
    </form>
  )
}

function PartnerSignup() {
  const loginAfterSignup = useLoginAfterSignup("partner")
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<PartnerValues>({ resolver: zodResolver(partnerSchema) })

  async function onSubmit(values: PartnerValues) {
    try {
      await api.partner.registerDeliveryPartner({
        ...values,
        serviceable_zip_codes: parseZipCodes(values.serviceable_zip_codes),
      })
      await loginAfterSignup(values.email, values.password)
    } catch (error) {
      setError("root", { message: getErrorMessage(error) })
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      <FieldGroup>
        <FormField id="name" label="Name" error={errors.name}>
          <Input id="name" aria-invalid={!!errors.name} {...register("name")} />
        </FormField>
        <FormField id="email" label="Email" error={errors.email}>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            aria-invalid={!!errors.email}
            {...register("email")}
          />
        </FormField>
        <FormField id="password" label="Password" error={errors.password}>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            aria-invalid={!!errors.password}
            {...register("password")}
          />
        </FormField>
        <FormField
          id="serviceable_zip_codes"
          label="Zip codes you deliver to"
          error={errors.serviceable_zip_codes}
        >
          <Input
            id="serviceable_zip_codes"
            placeholder="11001, 11002"
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
            placeholder="10"
            aria-invalid={!!errors.max_handling_capacity}
            {...register("max_handling_capacity", { valueAsNumber: true })}
          />
        </FormField>
        <SubmitButton isSubmitting={isSubmitting} error={errors.root} />
      </FieldGroup>
    </form>
  )
}

function SubmitButton({
  isSubmitting,
  error,
}: {
  isSubmitting: boolean
  error?: { message?: string }
}) {
  return (
    <Field>
      <FieldError errors={[error]} />
      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting && <Spinner />}
        Create account
      </Button>
    </Field>
  )
}
