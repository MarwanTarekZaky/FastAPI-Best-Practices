import "@/index.css"

import { QueryClientProvider } from "@tanstack/react-query"
import { ReactQueryDevtools } from "@tanstack/react-query-devtools"
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router"

import { queryClient } from "@/api/query-client"
import { AuthProvider } from "@/auth/auth-provider"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { AppRoutes } from "@/routes"

// Providers wrap the whole app, so every component can use what they give:
// cached API data, the login session, tooltips, and the current URL
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <TooltipProvider>
          <BrowserRouter>
            <AppRoutes />
          </BrowserRouter>
          <Toaster richColors position="top-right" />
        </TooltipProvider>
      </AuthProvider>
      {/* A panel to inspect the cache, only in development */}
      <ReactQueryDevtools />
    </QueryClientProvider>
  </StrictMode>,
)
