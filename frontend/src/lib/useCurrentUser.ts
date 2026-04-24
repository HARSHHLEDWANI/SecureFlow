import type { UserRole } from "@/config/sidebar";

export function useCurrentUser(): {
  id: string;
  role: UserRole;
} {
  return {
    id: "test-user",
    role: "ADMIN" as "ADMIN" | "USER", // 🔁 change USER / ADMIN to test
  };
}
