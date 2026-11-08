import { useState, type FormEvent } from "react"
import { Link, useNavigate } from "react-router"

import { useAuth } from "@/auth/auth-context"
import { Logo } from "@/components/logo"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export function HomePage() {
  const { session } = useAuth()
  const navigate = useNavigate()
  // One input doesn't need a form library, useState is enough
  const [trackingId, setTrackingId] = useState("")

  function handleTrack(event: FormEvent) {
    // Stop the browser from reloading the page, React Router changes the URL instead
    event.preventDefault()
    navigate(`/track/${trackingId.trim()}`)
  }

  return (
    <div className="flex min-h-svh flex-col">
      <header className="flex items-center justify-between p-4 md:px-10">
        <Logo />
        <nav className="flex gap-2">
          {session ? (
            <Button asChild>
              <Link to={`/${session.role}`}>Dashboard</Link>
            </Button>
          ) : (
            <>
              <Button variant="ghost" asChild>
                <Link to="/login">Log in</Link>
              </Button>
              <Button asChild>
                <Link to="/signup">Sign up</Link>
              </Button>
            </>
          )}
        </nav>
      </header>

      <main className="flex flex-1 flex-col items-center justify-center gap-8 p-6 text-center">
        <div className="flex max-w-2xl flex-col gap-4">
          <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">
            Ship it fast, track it live
          </h1>
          <p className="text-lg text-muted-foreground">
            Sellers create shipments, delivery partners bring them to the door, and
            clients follow every step.
          </p>
        </div>
        <form onSubmit={handleTrack} className="flex w-full max-w-md gap-2">
          <Input
            aria-label="Tracking id"
            placeholder="Paste your tracking id"
            value={trackingId}
            onChange={(event) => setTrackingId(event.target.value)}
          />
          <Button type="submit" disabled={!trackingId.trim()}>
            Track
          </Button>
        </form>
      </main>
    </div>
  )
}
