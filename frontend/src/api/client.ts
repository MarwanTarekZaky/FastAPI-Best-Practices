import axios from "axios"

import { Api } from "@/api/generated"
import { clearSession, getSession } from "@/auth/session"


const baseURL = import.meta.env.VITE_API_URL ?? "/api"

export const api = new Api({
    baseURL,
    securityWorker: () => {
        const session = getSession()
        if (session) {
            return { headers: {Authorization: `Bearer ${session.token}`}}
        }
    },
})

api.instance.interceptors.response.use(undefined, (error) => {
    const sentToken = axios.isAxiosError(error) && error.config?.headers.Authorization
    if (sentToken && error.response?.status == 401) {
        clearSession()
        window.location.assign("/login?expired=1")
    }
    return Promise.reject(error)
})