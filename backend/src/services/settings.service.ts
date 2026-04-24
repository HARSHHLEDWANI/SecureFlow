import crypto from "crypto";
import bcrypt from "bcryptjs";
import { prisma } from "../lib/prisma";
import { AppError } from "../middleware/errorHandler";

export async function getUserProfile(userId: string) {
  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: {
      id: true,
      email: true,
      role: true,
      createdAt: true,
      updatedAt: true,
      apiKeys: {
        select: { id: true, name: true, lastUsedAt: true, expiresAt: true, createdAt: true },
        orderBy: { createdAt: "desc" },
      },
    },
  });
  if (!user) throw new AppError(404, "User not found");
  return user;
}

export async function updateUserProfile(userId: string, data: { email?: string }) {
  if (data.email) {
    const existing = await prisma.user.findUnique({ where: { email: data.email } });
    if (existing && existing.id !== userId) {
      throw new AppError(409, "Email already in use");
    }
  }

  return prisma.user.update({
    where: { id: userId },
    data: { email: data.email },
    select: { id: true, email: true, role: true, updatedAt: true },
  });
}

export async function createApiKey(userId: string, name: string) {
  const plaintext = `sf_${crypto.randomBytes(32).toString("hex")}`;
  const hashedKey = crypto.createHash("sha256").update(plaintext).digest("hex");

  const key = await prisma.apiKey.create({
    data: { userId, hashedKey, name },
    select: { id: true, name: true, createdAt: true },
  });

  return { ...key, key: plaintext };
}

export async function revokeApiKey(userId: string, keyId: string) {
  const key = await prisma.apiKey.findUnique({ where: { id: keyId } });
  if (!key || key.userId !== userId) throw new AppError(404, "API key not found");
  await prisma.apiKey.delete({ where: { id: keyId } });
}
