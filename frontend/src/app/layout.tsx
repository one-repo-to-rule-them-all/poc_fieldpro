import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { Toaster } from "@/components/ui/toaster";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

const appName = process.env.NEXT_PUBLIC_APP_NAME ?? "FieldPro";

export const metadata: Metadata = {
  title: {
    template: `%s | ${appName}`,
    default: appName,
  },
  description:
    "Field service management platform for modern service businesses. Manage work orders, crews, clients, and invoices in one place.",
  applicationName: appName,
  keywords: ["field service", "work orders", "crew management", "invoicing"],
  authors: [{ name: appName }],
  robots: "noindex, nofollow", // SaaS app — don't index auth'd pages
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  themeColor: "#2563eb",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen bg-neutral-50 font-sans antialiased">
        <Providers>
          {children}
          <Toaster />
        </Providers>
      </body>
    </html>
  );
}
