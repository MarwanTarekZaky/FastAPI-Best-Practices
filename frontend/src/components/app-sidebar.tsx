import {
  LayoutDashboardIcon,
  PackagePlusIcon,
  TruckIcon,
  UserCogIcon,
} from "lucide-react"
import { Link } from "react-router"

import { useRole } from "@/auth/auth-context"
import type { Role } from "@/auth/session"
import { NavMain, type NavItem } from "@/components/nav-main"
import { NavUser } from "@/components/nav-user"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar"

// The pages each role can open from the sidebar
const NAV_ITEMS: Record<Role, NavItem[]> = {
  seller: [
    { title: "Dashboard", url: "/seller", icon: <LayoutDashboardIcon /> },
    { title: "New shipment", url: "/seller/shipments/new", icon: <PackagePlusIcon /> },
  ],
  partner: [
    { title: "Dashboard", url: "/partner", icon: <LayoutDashboardIcon /> },
    { title: "Profile", url: "/partner/profile", icon: <UserCogIcon /> },
  ],
}

export function AppSidebar(props: React.ComponentProps<typeof Sidebar>) {
  const role = useRole()

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link to={`/${role}`}>
                <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                  <TruckIcon className="size-4" />
                </div>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-medium">FastShip</span>
                  <span className="truncate text-xs">
                    {role === "seller" ? "Seller" : "Delivery partner"}
                  </span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={NAV_ITEMS[role]} />
      </SidebarContent>
      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
