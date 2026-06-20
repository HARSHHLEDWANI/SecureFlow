import { Request, Response, NextFunction } from "express";
import * as settingsService from "../services/settings.service";

export async function getProfile(req: Request, res: Response, next: NextFunction) {
  try {
    const data = await settingsService.getUserProfile(req.user!.userId);
    res.json({ success: true, data, error: null });
  } catch (err) {
    next(err);
  }
}

export async function updateProfile(req: Request, res: Response, next: NextFunction) {
  try {
    const data = await settingsService.updateUserProfile(req.user!.userId, req.body);
    res.json({ success: true, data, error: null });
  } catch (err) {
    next(err);
  }
}

export async function createApiKey(req: Request, res: Response, next: NextFunction) {
  try {
    const { name } = req.body;
    if (!name) {
      res.status(400).json({ success: false, data: null, error: "name is required" });
      return;
    }
    const data = await settingsService.createApiKey(req.user!.userId, name);
    res.status(201).json({ success: true, data, error: null });
  } catch (err) {
    next(err);
  }
}

export async function revokeApiKey(req: Request, res: Response, next: NextFunction) {
  try {
    await settingsService.revokeApiKey(req.user!.userId, String(req.params.id));
    res.json({ success: true, data: null, error: null });
  } catch (err) {
    next(err);
  }
}
