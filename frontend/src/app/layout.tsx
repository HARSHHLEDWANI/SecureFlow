import "./globals.css";
import type { Metadata } from "next";
import localFont from "next/font/local";
import { Toaster } from "sonner";
import { AuthProvider } from "@/lib/auth";

// Self-hosted Inter (variable) so the build has zero external network dependency
// and works in network-restricted CI/build environments (unlike next/font/google,
// which fetches from Google Fonts at build time).
const inter = localFont({
  src: "./fonts/InterVariable.woff2",
  variable: "--font-inter",
  display: "swap",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "SecureFlow — UPI Fraud Detection",
  description:
    "Real-time fraud detection for UPI transactions using machine learning, Redis, and a tamper-evident blockchain audit trail.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} antialiased`}>
        <AuthProvider>{children}</AuthProvider>
        <Toaster theme="dark" position="bottom-right" richColors closeButton />
      </body>
    </html>
  );
}
