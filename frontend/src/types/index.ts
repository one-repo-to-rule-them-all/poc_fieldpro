export type UserRole =
  | "platform_owner"
  | "tenant_admin"
  | "manager"
  | "employee"
  | "client_user";

export type WorkOrderStatus =
  | "draft"
  | "scheduled"
  | "in_progress"
  | "completed"
  | "cancelled"
  | "on_hold";

export type Priority = "low" | "normal" | "high" | "urgent";

export type InvoiceStatus =
  | "draft"
  | "sent"
  | "viewed"
  | "partial"
  | "paid"
  | "overdue"
  | "void";

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: UserRole;
  tenant_id: string;
  is_active: boolean;
  phone?: string;
  avatar_url?: string;
}

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  logo_url?: string;
  is_active: boolean;
}

export interface Client {
  id: string;
  tenant_id: string;
  name: string;
  code: string;
  industry?: string;
  is_active: boolean;
  billing_email?: string;
  billing_phone?: string;
  billing_address?: Record<string, string>;
  notes?: string;
  location_count?: number;
  created_at?: string;
  updated_at?: string;
  contacts?: ClientContact[];
}

export interface ClientContact {
  id: string;
  name: string;
  email?: string;
  phone?: string;
  title?: string;
  is_primary: boolean;
}

export interface Location {
  id: string;
  client_id: string;
  name: string;
  address: Address;
  latitude?: number;
  longitude?: number;
  geofence_radius_meters: number;
  is_active: boolean;
  qr_code_token: string;
}

export interface Address {
  street: string;
  city: string;
  state: string;
  zip: string;
  country: string;
}

export interface Crew {
  id: string;
  tenant_id?: string;
  name: string;
  code: string;
  description?: string;
  is_active: boolean;
  member_count?: number;
  lead_name?: string | null;
  members?: CrewMember[];
  created_at?: string;
  updated_at?: string;
}

export interface CrewMemberUser {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
}

export interface CrewMember {
  id: string;
  crew_id: string;
  user_id: string;
  user?: CrewMemberUser;
  role: "lead" | "member";
  joined_at: string;
  left_at?: string | null;
  is_active: boolean;
}

export type WorkType = "one_time" | "recurring";

export interface WorkOrder {
  id: string;
  title: string;
  description?: string;
  client_id: string;
  client_name?: string;
  location_id: string;
  location_name?: string;
  crew_id?: string;
  crew_name?: string;
  status: WorkOrderStatus;
  priority: Priority;
  work_type?: WorkType;
  scheduled_date: string;
  scheduled_start_time?: string;
  scheduled_end_time?: string;
  estimated_hours?: number;
  actual_hours?: number;
  sla_deadline?: string;
  sla_met?: boolean;
  recurrence_rule?: string;
  parent_work_order_id?: string;
  tasks?: WorkOrderTask[];
  check_ins?: CheckIn[];
  updated_at?: string;
}

export interface WorkOrderTask {
  id: string;
  title: string;
  is_required: boolean;
  status: "pending" | "completed" | "skipped" | "blocked";
  sort_order: number;
  skip_reason?: string;
}

export interface CheckIn {
  id: string;
  user_id: string;
  check_in_time: string;
  check_out_time?: string;
  is_valid: boolean;
  distance_from_location_meters?: number;
}

export interface Invoice {
  id: string;
  invoice_number: string;
  client_id: string;
  client_name?: string;
  status: InvoiceStatus;
  issue_date: string;
  due_date: string;
  subtotal: number;
  tax_rate?: number;
  tax_amount: number;
  discount_amount: number;
  total: number;
  amount_paid?: number;
  amount_due?: number;
  notes?: string;
  terms?: string;
  sent_at?: string;
  paid_at?: string;
  line_items?: InvoiceLineItem[];
}

export interface InvoiceLineItem {
  id: string;
  description: string;
  quantity: number;
  unit_price: number;
  line_total: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface KPIData {
  completion_rate: number;
  sla_compliance: number;
  active_work_orders: number;
  completed_today: number;
  outstanding_invoices: number;
  total_revenue_mtd: number;
  crew_utilization: number;
  avg_time_on_site_minutes: number;
}

export interface ApiError {
  message: string;
  status: number;
  code?: string;
  details?: Record<string, string[]>;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  user: User;
  tenant: Tenant;
}

export interface WorkOrderFilters {
  status?: WorkOrderStatus;
  priority?: Priority;
  client_id?: string;
  crew_id?: string;
  scheduled_date_from?: string;
  scheduled_date_to?: string;
  search?: string;
  page?: number;
  page_size?: number;
  /** Field-worker shortcut: return only work orders assigned to the current user */
  assigned_to_me?: boolean;
}

export interface ClientFilters {
  search?: string;
  is_active?: boolean;
  industry?: string;
  page?: number;
  page_size?: number;
}

export interface InvoiceFilters {
  status?: InvoiceStatus;
  client_id?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

export interface Notification {
  id: string;
  title: string;
  message: string;
  type: "info" | "success" | "warning" | "error";
  read: boolean;
  created_at: string;
}

export interface AnalyticsDateRange {
  from: string;
  to: string;
}

export interface WorkOrderTrend {
  date: string;
  completed: number;
  created: number;
}

export interface RevenueByClient {
  client_name: string;
  revenue: number;
}

export interface CrewProductivity {
  crew_name: string;
  work_orders_completed: number;
  avg_hours: number;
  sla_compliance: number;
}

export interface CheckInPayload {
  latitude: number;
  longitude: number;
  qr_code_token?: string;
}

export interface CompleteTaskPayload {
  status?: "completed" | "pending" | "skipped";
  notes?: string;
  skip_reason?: string;
}
