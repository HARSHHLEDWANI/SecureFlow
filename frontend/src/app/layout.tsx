import "./globals.css";
import ClientLayout from "./ClientLayout";
import { AuthProvider } from "@/context/auth";

export const metadata = {
  title: "SecureFlow",
  description: "AI + Blockchain Fraud Detection Platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-slate-950 antialiased">
        <AuthProvider>
          <ClientLayout>{children}</ClientLayout>
        </AuthProvider>
      </body>
    </html>
  );
}
