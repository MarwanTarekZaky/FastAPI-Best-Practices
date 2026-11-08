import type { ReactNode } from "react"
import { Link, useLocation } from "react-router"

import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"

export interface NavItem {
  title: string
  url: string
  icon: ReactNode
}

export function NavMain({ items }: { items: NavItem[] }) {
  const { pathname } = useLocation()
  const { setOpenMobile } = useSidebar()

  return (
    <SidebarGroup>
      <SidebarGroupLabel>Menu</SidebarGroupLabel>
      <SidebarMenu>
        {items.map((item) => (
          <SidebarMenuItem key={item.url}>
            {/* asChild: the button's style goes on the Link, so it's one clickable link */}
            <SidebarMenuButton asChild isActive={pathname === item.url} tooltip={item.title}>
              {/* On phones the sidebar is a drawer, close it after a click */}
              <Link to={item.url} onClick={() => setOpenMobile(false)}>
                {item.icon}
                <span>{item.title}</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        ))}
      </SidebarMenu>
    </SidebarGroup>
  )
}
