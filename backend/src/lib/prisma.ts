import dotenv from "dotenv";
dotenv.config(); // ✅ MUST be first

import { PrismaClient } from "@prisma/client";

export const prisma = new PrismaClient();
