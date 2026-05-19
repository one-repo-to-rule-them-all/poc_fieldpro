import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from "axios";
import Cookies from "js-cookie";
import type {
  PaginatedResponse,
  Client,
  ClientFilters,
  WorkOrder,
  WorkOrderFilters,
  Invoice,
  InvoiceFilters,
  Location,
  Crew,
  CrewMember,
  User,
  KPIData,
  LoginResponse,
  CheckInPayload,
  CompleteTaskPayload,
  WorkOrderTrend,
  RevenueByClient,
  CrewProductivity,
  AnalyticsDateRange,
  ApiError,
} from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// In-memory access token (not persisted for security)
let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

const api: AxiosInstance = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true,
});

// Request interceptor — attach Bearer token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = accessToken;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

let isRefreshing = false;
let refreshQueue: Array<{
  resolve: (token: string) => void;
  reject: (err: unknown) => void;
}> = [];

function processQueue(error: unknown, token: string | null): void {
  refreshQueue.forEach((p) => {
    if (error) {
      p.reject(error);
    } else if (token) {
      p.resolve(token);
    }
  });
  refreshQueue = [];
}

// Response interceptor — handle 401 with token refresh
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
    };

    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      // Never intercept 401s on the auth endpoints themselves — let those
      // propagate as real errors (wrong password, expired token, etc.)
      !originalRequest.url?.includes("/auth/login") &&
      !originalRequest.url?.includes("/auth/register") &&
      !originalRequest.url?.includes("/auth/refresh")
    ) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          refreshQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return api(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // The refresh_token cookie is HttpOnly, so js-cookie can't read it.
        // Send an empty body and rely on withCredentials to attach the cookie —
        // the backend's _get_refresh_token resolves it from either body or
        // cookie. The js-cookie read here is a best-effort hint for mobile
        // clients (where the cookie isn't HttpOnly).
        const refreshToken = Cookies.get("refresh_token");
        const response = await axios.post<{ access_token: string }>(
          `${API_URL}/api/v1/auth/refresh`,
          refreshToken ? { refresh_token: refreshToken } : {},
          { withCredentials: true }
        );

        const newToken = response.data.access_token;
        setAccessToken(newToken);
        processQueue(null, newToken);

        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        setAccessToken(null);
        Cookies.remove("refresh_token");
        if (typeof window !== "undefined") {
          window.location.href = "/login";
        }
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    // Normalize error
    const apiError: ApiError = {
      message:
        (error.response?.data as { detail?: string })?.detail ??
        error.message ??
        "An unexpected error occurred",
      status: error.response?.status ?? 0,
      code: (error.response?.data as { code?: string })?.code,
      details: (error.response?.data as { details?: Record<string, string[]> })
        ?.details,
    };

    return Promise.reject(apiError);
  }
);

// ─── Auth API ────────────────────────────────────────────────────────────────

export const authApi = {
  login: async (email: string, password: string): Promise<LoginResponse> => {
    const response = await api.post<LoginResponse>("/api/v1/auth/login", {
      email,
      password,
    });
    return response.data;
  },

  register: async (data: {
    company_name: string;
    first_name: string;
    last_name: string;
    email: string;
    password: string;
  }): Promise<LoginResponse> => {
    const response = await api.post<LoginResponse>("/api/v1/auth/register", data);
    return response.data;
  },

  logout: async (): Promise<void> => {
    await api.post("/api/v1/auth/logout");
  },

  refreshToken: async (
    refreshToken: string
  ): Promise<{ access_token: string }> => {
    const response = await axios.post<{ access_token: string }>(
      `${API_URL}/api/v1/auth/refresh`,
      { refresh_token: refreshToken },
      { withCredentials: true }
    );
    return response.data;
  },

  me: async () => {
    const response = await api.get<{ user: import("@/types").User; tenant: import("@/types").Tenant }>("/api/v1/auth/me");
    return response.data;
  },

  updateProfile: async (data: {
    first_name?: string;
    last_name?: string;
    phone?: string;
  }): Promise<import("@/types").User> => {
    const response = await api.patch<import("@/types").User>("/api/v1/auth/me", data);
    return response.data;
  },

  changePassword: async (data: {
    current_password: string;
    new_password: string;
  }): Promise<void> => {
    await api.post("/api/v1/auth/me/change-password", data);
  },
};

// ─── Clients API ─────────────────────────────────────────────────────────────

export const clientsApi = {
  list: async (
    params?: ClientFilters
  ): Promise<PaginatedResponse<Client>> => {
    const response = await api.get<PaginatedResponse<Client>>("/api/v1/clients", {
      params,
    });
    return response.data;
  },

  get: async (id: string): Promise<Client> => {
    const response = await api.get<Client>(`/api/v1/clients/${id}`);
    return response.data;
  },

  create: async (
    data: Omit<Client, "id" | "tenant_id" | "contacts">
  ): Promise<Client> => {
    const response = await api.post<Client>("/api/v1/clients", data);
    return response.data;
  },

  update: async (
    id: string,
    data: Partial<Omit<Client, "id" | "tenant_id">>
  ): Promise<Client> => {
    const response = await api.patch<Client>(`/api/v1/clients/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/api/v1/clients/${id}`);
  },

  listLocations: async (
    clientId: string,
    params?: { is_active?: boolean; page?: number; page_size?: number }
  ): Promise<PaginatedResponse<Location>> => {
    const response = await api.get<PaginatedResponse<Location>>(
      `/api/v1/clients/${clientId}/locations`,
      { params }
    );
    return response.data;
  },

  listWorkOrders: async (
    clientId: string,
    params?: { status?: string; page?: number; page_size?: number }
  ): Promise<PaginatedResponse<WorkOrder>> => {
    const response = await api.get<PaginatedResponse<WorkOrder>>(
      `/api/v1/clients/${clientId}/work-orders`,
      { params }
    );
    return response.data;
  },
};

// ─── Locations API ────────────────────────────────────────────────────────────

export const locationsApi = {
  list: async (
    params?: { client_id?: string; is_active?: boolean; page?: number; page_size?: number }
  ): Promise<PaginatedResponse<Location>> => {
    const response = await api.get<PaginatedResponse<Location>>(
      "/api/v1/locations",
      { params }
    );
    return response.data;
  },

  get: async (id: string): Promise<Location> => {
    const response = await api.get<Location>(`/api/v1/locations/${id}`);
    return response.data;
  },

  create: async (
    data: Omit<Location, "id" | "qr_code_token">
  ): Promise<Location> => {
    const response = await api.post<Location>("/api/v1/locations", data);
    return response.data;
  },

  update: async (
    id: string,
    data: Partial<Omit<Location, "id" | "qr_code_token">>
  ): Promise<Location> => {
    const response = await api.patch<Location>(`/api/v1/locations/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/api/v1/locations/${id}`);
  },
};

// ─── Work Orders API ──────────────────────────────────────────────────────────

export const workOrdersApi = {
  list: async (
    params?: WorkOrderFilters
  ): Promise<PaginatedResponse<WorkOrder>> => {
    const response = await api.get<PaginatedResponse<WorkOrder>>(
      "/api/v1/work-orders",
      { params }
    );
    return response.data;
  },

  get: async (id: string): Promise<WorkOrder> => {
    const response = await api.get<WorkOrder>(`/api/v1/work-orders/${id}`);
    return response.data;
  },

  create: async (
    data: Omit<WorkOrder, "id" | "tasks" | "check_ins" | "sla_met" | "actual_hours">
  ): Promise<WorkOrder> => {
    const response = await api.post<WorkOrder>("/api/v1/work-orders", data);
    return response.data;
  },

  update: async (
    id: string,
    data: Partial<Omit<WorkOrder, "id" | "check_ins">>
  ): Promise<WorkOrder> => {
    const response = await api.patch<WorkOrder>(
      `/api/v1/work-orders/${id}`,
      data
    );
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/api/v1/work-orders/${id}`);
  },

  checkIn: async (id: string, data: CheckInPayload): Promise<WorkOrder> => {
    const response = await api.post<WorkOrder>(
      `/api/v1/work-orders/${id}/check-in`,
      data
    );
    return response.data;
  },

  checkOut: async (id: string, data: { latitude: number; longitude: number }): Promise<WorkOrder> => {
    const response = await api.post<WorkOrder>(
      `/api/v1/work-orders/${id}/check-out`,
      data
    );
    return response.data;
  },

  addTask: async (
    woId: string,
    data: { title: string; description?: string; is_required?: boolean; sort_order?: number }
  ): Promise<WorkOrder> => {
    const response = await api.post<WorkOrder>(
      `/api/v1/work-orders/${woId}/tasks`,
      data
    );
    return response.data;
  },

  completeTask: async (
    woId: string,
    taskId: string,
    data: CompleteTaskPayload
  ): Promise<WorkOrder> => {
    const derivedStatus = data.status ?? (data.skip_reason ? "skipped" : "completed");
    const { status: _s, ...rest } = data;
    const response = await api.patch<WorkOrder>(
      `/api/v1/work-orders/${woId}/tasks/${taskId}`,
      { status: derivedStatus, ...rest }
    );
    return response.data;
  },

  completeWorkOrder: async (woId: string, notes?: string): Promise<WorkOrder> => {
    const response = await api.post<WorkOrder>(
      `/api/v1/work-orders/${woId}/complete`,
      null,
      { params: notes ? { completion_notes: notes } : undefined }
    );
    return response.data;
  },

  uploadAttachment: async (
    woId: string,
    file: File,
    onProgress?: (progress: number) => void
  ): Promise<{ url: string; filename: string }> => {
    const formData = new FormData();
    formData.append("file", file);
    const response = await api.post<{ url: string; filename: string }>(
      `/api/v1/work-orders/${woId}/attachments`,
      formData,
      {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (progressEvent) => {
          if (onProgress && progressEvent.total) {
            const progress = Math.round(
              (progressEvent.loaded * 100) / progressEvent.total
            );
            onProgress(progress);
          }
        },
      }
    );
    return response.data;
  },
};

// ─── Crews API ────────────────────────────────────────────────────────────────

export const crewsApi = {
  list: async (
    params?: { page?: number; page_size?: number; search?: string }
  ): Promise<PaginatedResponse<Crew>> => {
    const response = await api.get<PaginatedResponse<Crew>>("/api/v1/crews", {
      params,
    });
    return response.data;
  },

  get: async (id: string): Promise<Crew> => {
    const response = await api.get<Crew>(`/api/v1/crews/${id}`);
    return response.data;
  },

  create: async (data: Omit<Crew, "id" | "members">): Promise<Crew> => {
    const response = await api.post<Crew>("/api/v1/crews", data);
    return response.data;
  },

  update: async (
    id: string,
    data: Partial<Omit<Crew, "id">>
  ): Promise<Crew> => {
    const response = await api.patch<Crew>(`/api/v1/crews/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/api/v1/crews/${id}`);
  },

  addMember: async (
    crewId: string,
    data: { user_id: string; role?: "lead" | "member" }
  ): Promise<CrewMember> => {
    const response = await api.post<CrewMember>(
      `/api/v1/crews/${crewId}/members`,
      data
    );
    return response.data;
  },

  removeMember: async (
    crewId: string,
    userId: string
  ): Promise<CrewMember> => {
    const response = await api.delete<CrewMember>(
      `/api/v1/crews/${crewId}/members/${userId}`
    );
    return response.data;
  },
};

// ─── Users API (read-only listing for member pickers) ────────────────────────

export const usersApi = {
  list: async (params?: {
    search?: string;
    role?: string;
    is_active?: boolean;
    page?: number;
    limit?: number;
  }): Promise<{ data: User[]; meta: { total: number; page: number; limit: number; pages: number } }> => {
    const response = await api.get<{ data: User[]; meta: { total: number; page: number; limit: number; pages: number } }>(
      "/api/v1/users",
      { params }
    );
    return response.data;
  },
};

// ─── Invoices API ─────────────────────────────────────────────────────────────

export const invoicesApi = {
  list: async (
    params?: InvoiceFilters
  ): Promise<PaginatedResponse<Invoice>> => {
    const response = await api.get<PaginatedResponse<Invoice>>(
      "/api/v1/invoices",
      { params }
    );
    return response.data;
  },

  get: async (id: string): Promise<Invoice> => {
    const response = await api.get<Invoice>(`/api/v1/invoices/${id}`);
    return response.data;
  },

  create: async (
    data: Omit<Invoice, "id" | "invoice_number" | "line_items">
  ): Promise<Invoice> => {
    const response = await api.post<Invoice>("/api/v1/invoices", data);
    return response.data;
  },

  update: async (
    id: string,
    data: Partial<Omit<Invoice, "id" | "invoice_number">>
  ): Promise<Invoice> => {
    const response = await api.patch<Invoice>(`/api/v1/invoices/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/api/v1/invoices/${id}`);
  },

  generateFromWorkOrders: async (workOrderIds: string[]): Promise<Invoice> => {
    const response = await api.post<Invoice>(
      "/api/v1/invoices/generate-from-work-orders",
      { work_order_ids: workOrderIds }
    );
    return response.data;
  },
};

// ─── Analytics API ────────────────────────────────────────────────────────────

export const analyticsApi = {
  getKPIs: async (params?: AnalyticsDateRange): Promise<KPIData> => {
    const response = await api.get<KPIData>("/api/v1/analytics/kpis", { params });
    return response.data;
  },

  getWorkOrderTrends: async (
    params: AnalyticsDateRange
  ): Promise<WorkOrderTrend[]> => {
    const response = await api.get<WorkOrderTrend[]>(
      "/api/v1/analytics/work-order-trends",
      { params }
    );
    return response.data;
  },

  getRevenueByClient: async (
    params: AnalyticsDateRange
  ): Promise<RevenueByClient[]> => {
    const response = await api.get<RevenueByClient[]>(
      "/api/v1/analytics/revenue-by-client",
      { params }
    );
    return response.data;
  },

  getCrewProductivity: async (
    params: AnalyticsDateRange
  ): Promise<CrewProductivity[]> => {
    const response = await api.get<CrewProductivity[]>(
      "/api/v1/analytics/crew-productivity",
      { params }
    );
    return response.data;
  },
};

export default api;
