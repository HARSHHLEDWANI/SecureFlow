import { redirect } from "next/navigation";

export function requireRole(
  userRole: "USER" | "ADMIN",
  allowed: ("USER" | "ADMIN")[]
) {
  if (!allowed.includes(userRole)) {
    redirect("/unauthorized");
  }
}
