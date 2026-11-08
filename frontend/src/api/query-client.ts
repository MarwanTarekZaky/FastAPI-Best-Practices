import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query"
import axios from "axios"
import { toast } from "sonner"

import { getErrorMessage } from "@/api/errors"

export const queryClient = new QueryClient({
  // Every failed request shows a toast, so pages don't repeat this code.
  // A query can turn it off with meta: { showErrorToast: false }
  queryCache: new QueryCache({
    onError: (error, query) => {
      if (query.meta?.showErrorToast !== false) {
        toast.error(getErrorMessage(error))
      }
    },
  }),
  mutationCache: new MutationCache({
    onError: (error) => toast.error(getErrorMessage(error)),
  }),
  defaultOptions: {
    queries: {
      // Data younger than 30 seconds is shown without asking the API again
      staleTime: 30_000,
      // Try again after network or server errors, but not after 4xx errors:
      // asking again for a missing shipment gives the same answer
      retry: (failureCount, error) => {
        const status = axios.isAxiosError(error) ? error.response?.status : undefined
        return failureCount < 2 && (status === undefined || status >= 500)
      },
    },
  },
})
