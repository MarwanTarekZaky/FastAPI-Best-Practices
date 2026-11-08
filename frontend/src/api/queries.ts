import {
  skipToken,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { toast } from "sonner"

import { api } from "@/api/client"
import type {
  DeliveryPartnerRead,
  DeliveryPartnerUpdate,
  SellerRead,
  ShipmentCreate,
  ShipmentRead,
  ShipmentUpdate,
  TagName,
} from "@/api/generated"
import type { Role } from "@/auth/session"

// React Query saves each answer under a key. Invalidating a key refetches it,
// and ["shipments"] also matches every key that starts with it
export const queryKeys = {
  profile: (role: Role) => ["profile", role] as const,
  myShipments: (role: Role) => ["shipments", role] as const,
  tagShipments: (tag: TagName | null) => ["shipments", "seller", "tag", tag] as const,
  shipment: (id: string) => ["shipment", id] as const,
  tags: ["tags"] as const,
}

// Queries: read data

// Sellers and partners have different fields, but both have a name and an email
export function useProfile(role: Role) {
  return useQuery<SellerRead | DeliveryPartnerRead>({
    queryKey: queryKeys.profile(role),
    queryFn: () =>
      role === "seller" ? api.seller.getSellerProfile() : api.partner.getPartnerProfile(),
  })
}

export function usePartnerProfile() {
  return useQuery({
    queryKey: queryKeys.profile("partner"),
    queryFn: () => api.partner.getPartnerProfile(),
  })
}

export function useMyShipments(role: Role) {
  return useQuery({
    queryKey: queryKeys.myShipments(role),
    queryFn: () =>
      role === "seller"
        ? api.seller.getSellerShipments()
        : api.partner.getPartnerShipments(),
  })
}

export function useTagShipments(tag: TagName | null) {
  return useQuery({
    queryKey: queryKeys.tagShipments(tag),
    // skipToken: don't run until a tag is chosen
    queryFn: tag ? () => api.tag.getShipmentsByTag({ tag_name: tag }) : skipToken,
  })
}

export function useShipment(id: string, showErrorToast = true) {
  return useQuery({
    queryKey: queryKeys.shipment(id),
    queryFn: () => api.shipment.getShipment({ id }),
    meta: { showErrorToast },
  })
}

export function useTags() {
  return useQuery({
    queryKey: queryKeys.tags,
    queryFn: () => api.tag.getTags(),
    // The tags are fixed, no need to ask again
    staleTime: Infinity,
  })
}

// Mutations: change data

// After a change: show the new shipment right away and refresh the lists
function useShipmentChanged() {
  const queryClient = useQueryClient()

  return (shipment: ShipmentRead) => {
    queryClient.setQueryData(queryKeys.shipment(shipment.id), shipment)
    queryClient.invalidateQueries({ queryKey: ["shipments"] })
  }
}

export function useCreateShipment() {
  const onChanged = useShipmentChanged()

  return useMutation({
    mutationFn: (data: ShipmentCreate) => api.shipment.submitShipment(data),
    onSuccess: (shipment) => {
      onChanged(shipment)
      toast.success("Shipment created, the client got an email")
    },
  })
}

export function useUpdateShipment(id: string) {
  const onChanged = useShipmentChanged()

  return useMutation({
    mutationFn: (data: ShipmentUpdate) => api.shipment.updateShipment({ id }, data),
    onSuccess: (shipment) => {
      onChanged(shipment)
      toast.success("Shipment updated")
    },
  })
}

export function useVerifyDelivery(id: string) {
  const onChanged = useShipmentChanged()

  return useMutation({
    mutationFn: (code: string) => api.shipment.verifyDelivery({ id }, { code }),
    onSuccess: (shipment) => {
      onChanged(shipment)
      toast.success("Delivered!")
    },
  })
}

export function useResendCode(id: string) {
  return useMutation({
    mutationFn: () => api.shipment.resendVerificationCode({ id }),
    onSuccess: (message) => toast.success(message.detail),
  })
}

export function useCancelShipment(id: string) {
  const onChanged = useShipmentChanged()

  return useMutation({
    mutationFn: () => api.shipment.cancelShipment({ id }),
    onSuccess: (shipment) => {
      onChanged(shipment)
      toast.success("Shipment cancelled")
    },
  })
}

export function useAddTag(id: string) {
  const onChanged = useShipmentChanged()

  return useMutation({
    mutationFn: (tag: TagName) => api.shipment.addTag({ id, tag_name: tag }),
    onSuccess: onChanged,
  })
}

export function useRemoveTag(id: string) {
  const onChanged = useShipmentChanged()

  return useMutation({
    mutationFn: (tag: TagName) => api.shipment.removeTag({ id, tag_name: tag }),
    onSuccess: onChanged,
  })
}

export function useUpdatePartner() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: DeliveryPartnerUpdate) => api.partner.updateDeliveryPartner(data),
    onSuccess: (partner) => {
      queryClient.setQueryData(queryKeys.profile("partner"), partner)
      toast.success("Profile saved")
    },
  })
}
