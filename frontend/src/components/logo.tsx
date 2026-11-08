import { TruckIcon } from "lucide-react"
import { Link } from "react-router"

export function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2 font-medium">
      <div className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
        <TruckIcon className="size-4" />
      </div>
      FastShip
    </Link>
  )
}
