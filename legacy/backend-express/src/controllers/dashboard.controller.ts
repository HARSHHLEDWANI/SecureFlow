import { Request, Response, NextFunction } from "express";
import * as dashboardService from "../services/dashboard.service";

export async function stats(_req: Request, res: Response, next: NextFunction) {
  try {
    const data = await dashboardService.getDashboardStats();
    res.json({ success: true, data, error: null });
  } catch (err) {
    next(err);
  }
}
