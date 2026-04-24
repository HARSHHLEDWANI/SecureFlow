import axios from "axios";
import { logger } from "../lib/logger";

const AI_URL = process.env.AI_SERVICE_URL ?? "http://localhost:8000";

export interface AiPrediction {
  risk_score: number;
  confidence: number;
  explanation: string;
  features_used?: Record<string, unknown>;
}

export async function predictRisk(
  fromWallet: string,
  toWallet: string,
  amount: number,
  currency: string,
  velocityCount?: number
): Promise<AiPrediction | null> {
  try {
    const response = await axios.post<AiPrediction>(
      `${AI_URL}/predict-risk`,
      { fromWallet, toWallet, amount, currency, timestamp: new Date().toISOString(), velocityCount },
      { timeout: 5000 }
    );
    return response.data;
  } catch (err) {
    logger.warn({ err }, "AI service unavailable, proceeding without score");
    return null;
  }
}
