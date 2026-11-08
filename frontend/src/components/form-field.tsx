import type { ReactNode } from "react"

import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field"

// A label, the input passed as children, an optional hint and the error under it
export function FormField({
  id,
  label,
  error,
  description,
  children,
}: {
  id: string
  label: string
  error?: { message?: string }
  description?: string
  children: ReactNode
}) {
  return (
    <Field data-invalid={!!error}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      {children}
      {description && <FieldDescription>{description}</FieldDescription>}
      <FieldError errors={[error]} />
    </Field>
  )
}
