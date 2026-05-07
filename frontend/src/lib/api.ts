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
