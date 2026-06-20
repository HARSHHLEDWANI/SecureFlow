import { Request, Response, NextFunction } from "express";
import { verifyAccessToken, JwtPayload } from "../lib/jwt";
import { prisma } from "../lib/prisma";
import crypto from "crypto";

declare global {
  namespace Express {
    interface Request {
      user?: JwtPayload;
    }
  }
}

export async function requireAuth(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  const apiKey = req.headers["x-api-key"] as string | undefined;

  if (apiKey) {
    const hashedKey = crypto.createHash("sha256").update(apiKey).digest("hex");
    const key = await prisma.apiKey.findUnique({
      where: { hashedKey },
      include: { user: true },
    });

    if (key && (!key.expiresAt || key.expiresAt > new Date())) {
      await prisma.apiKey.update({
        where: { id: key.id },
        data: { lastUsedAt: new Date() },
      });
      req.user = {
        userId: key.user.id,
        email: key.user.email,
        role: key.user.role,
      };
      next();
      return;
    }
  }

  const authHeader = req.headers.authorization;
  if (!authHeader?.startsWith("Bearer ")) {
    res.status(401).json({ success: false, data: null, error: "Unauthorized" });
    return;
  }

  const token = authHeader.slice(7);
  try {
    req.user = verifyAccessToken(token);
    next();
  } catch {
    res.status(401).json({ success: false, data: null, error: "Token invalid or expired" });
  }
}

export function requireRole(...roles: string[]) {
  return (req: Request, res: Response, next: NextFunction): void => {
    if (!req.user || !roles.includes(req.user.role)) {
      res.status(403).json({ success: false, data: null, error: "Forbidden" });
      return;
    }
    next();
  };
}
