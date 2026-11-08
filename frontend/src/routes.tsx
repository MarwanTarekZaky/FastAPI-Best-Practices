import { Route, Routes } from "react-router"

import { RequireAuth } from "@/auth/require-auth"
import { DashboardLayout } from "@/layouts/dashboard-layout"
import { HomePage } from "@/pages/home-page"
import { LoginPage } from "@/pages/login-page"
import { NotFoundPage } from "@/pages/not-found-page"
import { PartnerDashboardPage } from "@/pages/partner/dashboard-page"
import { PartnerProfilePage } from "@/pages/partner/profile-page"
import { PartnerShipmentPage } from "@/pages/partner/shipment-page"
import { SellerDashboardPage } from "@/pages/seller/dashboard-page"
import { NewShipmentPage } from "@/pages/seller/new-shipment-page"
import { SellerShipmentPage } from "@/pages/seller/shipment-page"
import { SignupPage } from "@/pages/signup-page"
import { TrackPage } from "@/pages/track-page"

// Which page shows for which URL. A route without a path only wraps its children
export function AppRoutes() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/track/:id" element={<TrackPage />} />

      {/* Sellers only, inside the sidebar layout */}
      <Route element={<RequireAuth role="seller" />}>
        <Route element={<DashboardLayout />}>
          <Route path="/seller" element={<SellerDashboardPage />} />
          <Route path="/seller/shipments/new" element={<NewShipmentPage />} />
          <Route path="/seller/shipments/:id" element={<SellerShipmentPage />} />
        </Route>
      </Route>

      {/* Delivery partners only */}
      <Route element={<RequireAuth role="partner" />}>
        <Route element={<DashboardLayout />}>
          <Route path="/partner" element={<PartnerDashboardPage />} />
          <Route path="/partner/shipments/:id" element={<PartnerShipmentPage />} />
          <Route path="/partner/profile" element={<PartnerProfilePage />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
