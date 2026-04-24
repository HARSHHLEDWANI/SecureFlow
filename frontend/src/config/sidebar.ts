import {
  LayoutDashboard,
  CreditCard,
  ShieldAlert,
  Users,
  FileSearch,
} from "lucide-react";

export type UserRole = "USER" | "ADMIN";

export type SidebarItem = {
  label: string;
  href: string;
  icon: any;
};

export const sidebarConfig: Record<UserRole, SidebarItem[]> = {
  USER: [
    {
      label: "Dashboard",
      href: "/dashboard",
      icon: LayoutDashboard,
    },
    {
      label: "Transactions",
      href: "/transactions",
      icon: CreditCard,
    },
  ],

  ADMIN: [
    {
      label: "Dashboard",
      href: "/dashboard",
      icon: LayoutDashboard,
    },
    {
      label: "Transactions",
      href: "/transactions",
      icon: CreditCard,
    },
    {
      label: "Manual Reviews",
      href: "/reviews",
      icon: ShieldAlert,
    },
    {
      label: "Users",
      href: "/admin/users",
      icon: Users,
    },
    {
      label: "Audit Logs",
      href: "/audit",
      icon: FileSearch,
    },
  ],
};
