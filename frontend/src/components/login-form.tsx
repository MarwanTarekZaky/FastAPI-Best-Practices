import { zodResolver } from "@hookform/resolvers/zod"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { Link, useLocation, useNavigate, useSearchParams } from "react-router"
import { z } from "zod"

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

// The rules each field must follow, checked before anything is sent
const loginSchema = z.object({
  email: z.email("Enter a valid email"),
  password: z.string().min(1, "Enter your password"),
})

// The TypeScript type of the form values, made from the schema
type LoginValues = z.infer<typeof loginSchema>

export function LoginForm() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()

  const [role, setRole] = useState<Role>(
    searchParams.get("role") === "partner" ? "partner" : "seller",
  )

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) })

  async function onSubmit(values: LoginValues) {
    try {
      await login(role, values.email, values.password)
      // Back to the page that asked for a login, or to the dashboard
      const from = (location.state as { from?: string } | null)?.from
      navigate(from?.startsWith(`/${role}`) ? from : `/${role}`, { replace: true })
    } catch (error) {
      // "root" is for an error about the whole form, not one field
      setError("root", { message: getErrorMessage(error) })
    }
  }

  return (
    <Card>
      <CardHeader className="text-center">
        <CardTitle className="text-xl">Welcome back</CardTitle>
        <CardDescription>
          {searchParams.has("expired")
            ? "Your session expired, please log in again"
            : "Log in to your FastShip account"}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {/* handleSubmit checks the schema first, onSubmit only runs when it's valid */}
        <form onSubmit={handleSubmit(onSubmit)} noValidate>
          <FieldGroup>
            <Tabs value={role} onValueChange={(value) => setRole(value as Role)}>
              <TabsList className="w-full">
                <TabsTrigger value="seller">Seller</TabsTrigger>
                <TabsTrigger value="partner">Delivery partner</TabsTrigger>
              </TabsList>
            </Tabs>
            <FormField id="email" label="Email" error={errors.email}>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                autoComplete="email"
                aria-invalid={!!errors.email}
                {...register("email")}
              />
            </FormField>
            <FormField id="password" label="Password" error={errors.password}>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                aria-invalid={!!errors.password}
                {...register("password")}
              />
            </FormField>
            <Field>
              <FieldError errors={[errors.root]} />
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting && <Spinner />}
                Log in
              </Button>
              <FieldDescription className="text-center">
                Don&apos;t have an account? <Link to="/signup">Sign up</Link>
              </FieldDescription>
            </Field>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  )
}
