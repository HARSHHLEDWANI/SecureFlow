"use client";

import Link from "next/link";
import { sidebarConfig } from "@/config/sidebar";
import { useCurrentUser } from "@/lib/useCurrentUser";

export function Sidebar() {
  const user = useCurrentUser();
  const items = sidebarConfig[user.role];

  console.log("Sidebar rendered with role:", user.role);

  return (
    <aside className="w-64 h-screen border-r bg-white p-4">
      <div className="mb-6 text-xl font-semibold">SecureFlow</div>

      <nav className="space-y-1">
        {items.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="flex items-center gap-3 px-3 py-2 rounded hover:bg-gray-100 text-sm"
          >
            <item.icon className="w-4 h-4" />
            {item.label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
