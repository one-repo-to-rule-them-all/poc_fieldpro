import path from "node:path";

export type Role = "admin" | "manager" | "employee";

export interface RoleCredentials {
  email: string;
  password: string;
  role: Role;
}

export const ROLES: Record<Role, RoleCredentials> = {
  admin: {
    email: "admin@demo.fieldpro.app",
    password: "Admin123!",
    role: "admin",
  },
  manager: {
    email: "manager@demo.fieldpro.app",
    password: "Manager123!",
    role: "manager",
  },
  employee: {
    email: "carlos@demo.fieldpro.app",
    password: "Employee123!",
    role: "employee",
  },
};

const AUTH_DIR = path.join(__dirname, "..", ".auth");

export const AUTH_FILE: Record<Role, string> = {
  admin: path.join(AUTH_DIR, "admin.json"),
  manager: path.join(AUTH_DIR, "manager.json"),
  employee: path.join(AUTH_DIR, "employee.json"),
};

export const API_URL = process.env.API_URL ?? "http://localhost:8000";
