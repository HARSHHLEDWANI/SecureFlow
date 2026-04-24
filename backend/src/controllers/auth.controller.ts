import { Request, Response, NextFunction } from "express";
import * as authService from "../services/auth.service";

export async function login(req: Request, res: Response, next: NextFunction) {
  try {
    const result = await authService.login(req.body.email, req.body.password);
    res.cookie("refreshToken", result.refreshToken, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "strict",
      maxAge: 7 * 24 * 60 * 60 * 1000,
    });
    res.json({
      success: true,
      data: { accessToken: result.accessToken, user: result.user },
      error: null,
    });
  } catch (err) {
    next(err);
  }
}

export async function refresh(req: Request, res: Response, next: NextFunction) {
  try {
    const token = req.cookies?.refreshToken ?? req.body.refreshToken;
    if (!token) {
      res.status(401).json({ success: false, data: null, error: "No refresh token" });
      return;
    }
    const result = await authService.refreshAccess(token);
    res.cookie("refreshToken", result.refreshToken, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "strict",
      maxAge: 7 * 24 * 60 * 60 * 1000,
    });
    res.json({ success: true, data: { accessToken: result.accessToken }, error: null });
  } catch (err) {
    next(err);
  }
}

export function logout(req: Request, res: Response) {
  if (req.user) authService.logout(req.user.userId);
  res.clearCookie("refreshToken");
  res.json({ success: true, data: null, error: null });
}

export async function me(req: Request, res: Response, next: NextFunction) {
  try {
    const user = await authService.getMe(req.user!.userId);
    res.json({ success: true, data: user, error: null });
  } catch (err) {
    next(err);
  }
}
