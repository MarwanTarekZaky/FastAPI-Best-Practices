import { Navigate } from "react-router"

import { useAuth } from "@/auth/auth-context"
import { Logo } from "@/components/logo"
import { SignupForm } from "@/components/signup-form"

export function SignupPage() {
  const { session } = useAuth()

  if (session) {
    return <Navigate to={`/${session.role}`} replace />
  }

  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-6 bg-muted p-6 md:p-10">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <div className="self-center">
          <Logo />
        </div>
        <SignupForm />
      </div>
    </div>
  )
}
