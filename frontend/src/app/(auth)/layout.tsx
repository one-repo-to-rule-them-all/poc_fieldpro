import type { ReactNode } from "react";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-neutral-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-neutral-900">FieldPro</h1>
          <p className="text-neutral-500 text-sm mt-1">Field Service Management</p>
        </div>
        {children}
      </div>
    </div>
  );
}
