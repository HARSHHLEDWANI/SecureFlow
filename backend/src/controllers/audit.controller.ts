import { Request, Response, NextFunction } from "express";
import * as auditService from "../services/audit.service";

export async function list(req: Request, res: Response, next: NextFunction) {
  try {
    const limit = Math.min(Number(req.query.limit ?? 20), 100);
    const cursor = req.query.cursor ? String(req.query.cursor) : undefined;
    const action = req.query.action ? String(req.query.action) : undefined;

    const result = await auditService.listAuditLogs({ cursor, limit, action });
    res.json({
      success: true,
      data: result.items,
      error: null,
      meta: { nextCursor: result.nextCursor, hasMore: result.hasMore, limit },
    });
  } catch (err) {
    next(err);
  }
}

export async function auditStats(_req: Request, res: Response, next: NextFunction) {
  try {
    const data = await auditService.getAuditStats();
    res.json({ success: true, data, error: null });
  } catch (err) {
    next(err);
  }
}
