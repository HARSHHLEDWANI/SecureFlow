import { Router } from "express";
import { requireAuth } from "../middleware/auth";
import * as ctrl from "../controllers/audit.controller";

const router = Router();

router.use(requireAuth);
router.get("/", ctrl.list);
router.get("/stats", ctrl.auditStats);

export default router;
