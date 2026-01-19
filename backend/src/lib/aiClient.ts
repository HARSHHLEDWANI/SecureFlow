import axios from "axios";

const AI_BASE_URL = "http://localhost:8000";

export interface FraudPrediction {
  risk_score: number;
  confidence: number;
  explanation: string;
}

export const getFraudRiskSafe = async (payload: {
  fromWallet: string;
  toWallet: string;
  amount: number;
  currency: string;
}): Promise<FraudPrediction | null> => {
  try {
    const response = await axios.post(
      `${AI_BASE_URL}/predict-risk`,
      {
        from_wallet: payload.fromWallet,
        to_wallet: payload.toWallet,
        amount: payload.amount,
        currency: payload.currency,
      },
      { timeout: 3000 }
    );

    return response.data;
  } catch (error) {
    console.error("AI service unavailable:", error);
    return null; // 👈 graceful fallback
  }
};
