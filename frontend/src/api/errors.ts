import axios from "axios"

// FastAPI errors look like {"detail": "Shipment not found"}, and 422 errors like
// {"detail": [{"loc": ["body", "weight"], "msg": "Input should be ..."}]}
export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (!error.response) {
      return "Can't reach the server, is the API running?"
    }

    const detail = error.response.data?.detail
    if (typeof detail === "string") {
      return detail
    }
    if (Array.isArray(detail) && detail.length > 0) {
      const { loc, msg } = detail[0]
      return `${loc.at(-1)}: ${msg}`
    }
  }
  return "Something went wrong"
}
