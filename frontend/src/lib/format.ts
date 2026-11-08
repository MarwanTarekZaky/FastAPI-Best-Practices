import type { ShipmentStatus } from "@/api/generated"

export const STATUS_LABELS: Record<ShipmentStatus, string> = {
  placed: "Placed",
  in_transit: "In transit",
  out_for_delivery: "Out for delivery",
  delivered: "Delivered",
  cancelled: "Cancelled",
}

// Same rule as the API: nothing can change after these
export function isFinished(status: ShipmentStatus | null) {
  return status === "delivered" || status === "cancelled"
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))
}

// "temperature_controlled" -> "Temperature controlled"
export function formatTagName(name: string) {
  const words = name.replaceAll("_", " ")
  return words.charAt(0).toUpperCase() + words.slice(1)
}

// Zip codes typed as "11001, 11002"
export const ZIP_CODE_LIST = /^\s*\d+(\s*,\s*\d+)*\s*$/

export function parseZipCodes(text: string): number[] {
  return text.split(",").map((zipCode) => Number(zipCode.trim()))
}
