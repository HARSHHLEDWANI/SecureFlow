import { Router } from "express";
import { requireAuth } from "../middleware/auth";
import * as ctrl from "../controllers/settings.controller";

const router = Router();

router.use(requireAuth);
router.get("/", ctrl.getProfile);
router.put("/", ctrl.updateProfile);
router.post("/api-keys", ctrl.createApiKey);
router.delete("/api-keys/:id", ctrl.revokeApiKey);

export default router;
