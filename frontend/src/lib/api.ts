import axios, { AxiosError, type AxiosInstance } from "axios";

const baseURL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ApiError = {
  message: string;
  status: number;
  detail?: unknown;
};

let _token: string | null = null;

if (typeof window !== "undefined") {
  _token = window.localStorage.getItem("jump.token");
}

export function setToken(token: string | null): void {
  _token = token;
  if (typeof window !== "undefined") {
    if (token) window.localStorage.setItem("jump.token", token);
    else window.localStorage.removeItem("jump.token");
  }
}

export function getToken(): string | null {
  return _token;
}

export function createApiClient(): AxiosInstance {
  const instance = axios.create({ baseURL, timeout: 60_000 });
  instance.interceptors.request.use((config) => {
    const t = getToken();
    if (t) config.headers.Authorization = `Bearer ${t}`;
    return config;
  });
  instance.interceptors.response.use(
    (r) => r,
    (err: AxiosError) => {
      if (err.response?.status === 401 && typeof window !== "undefined") {
        setToken(null);
        // Redirect simples — Next.js ignora se já está em /login
        if (!window.location.pathname.startsWith("/login")) {
          window.location.assign("/login?expired=1");
        }
      }
      return Promise.reject(err);
    },
  );
  return instance;
}

export const api = createApiClient();

// F5.7 LGPD — helpers do /admin/data-requests. Mantidos como funções soltas
// para preservar o padrão do projeto (api.get/api.post diretos no resto do
// frontend); este é o primeiro recurso novo que justifica agrupamento por
// causa do número de operações (list/create manual/fulfill) que o admin opera.
import type {
  AdminDataRequestCreate,
  DataProcessingRecord,
  DataProcessingRecordList,
  DPRequestStatus,
  DPRequestType,
} from "./types";

export const apiAdminDataRequests = {
  async list(params: {
    status?: DPRequestStatus;
    request_type?: DPRequestType;
    page?: number;
    page_size?: number;
  }): Promise<DataProcessingRecordList> {
    const qs = new URLSearchParams();
    if (params.status) qs.set("status", params.status);
    if (params.request_type) qs.set("request_type", params.request_type);
    if (params.page) qs.set("page", String(params.page));
    if (params.page_size) qs.set("page_size", String(params.page_size));
    const suffix = qs.toString();
    const url = `/admin/data-requests${suffix ? `?${suffix}` : ""}`;
    const r = await api.get<DataProcessingRecordList>(url);
    return r.data;
  },

  async createManual(
    payload: AdminDataRequestCreate,
  ): Promise<DataProcessingRecord> {
    const r = await api.post<DataProcessingRecord>(
      "/admin/data-requests",
      payload,
    );
    return r.data;
  },

  async fulfill(id: string): Promise<DataProcessingRecord> {
    const r = await api.post<DataProcessingRecord>(
      `/admin/data-requests/${id}/fulfill`,
    );
    return r.data;
  },
};

export function asApiError(e: unknown): ApiError {
  if (e instanceof AxiosError) {
    const data = e.response?.data as { detail?: unknown } | undefined;
    const msg =
      typeof data?.detail === "string"
        ? data.detail
        : e.response?.statusText || e.message;
    return { message: msg, status: e.response?.status ?? 0, detail: data?.detail };
  }
  if (e instanceof Error) return { message: e.message, status: 0 };
  return { message: String(e), status: 0 };
}
