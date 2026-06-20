import request from "supertest";
import app from "../app";

let token: string;

beforeAll(async () => {
  const res = await request(app).post("/api/auth/login").send({
    email: "admin@secureflow.dev",
    password: "SecureFlow123!",
  });
  token = res.body.data.accessToken;
});

describe("Transactions endpoints", () => {
  it("GET /api/transactions — returns paginated list", async () => {
    const res = await request(app)
      .get("/api/transactions?limit=5")
      .set("Authorization", `Bearer ${token}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(Array.isArray(res.body.data)).toBe(true);
    expect(res.body.meta).toBeDefined();
    expect(res.body.meta.limit).toBe(5);
  });

  it("GET /api/transactions — filter by status", async () => {
    const res = await request(app)
      .get("/api/transactions?status=APPROVED")
      .set("Authorization", `Bearer ${token}`);

    expect(res.status).toBe(200);
    res.body.data.forEach((tx: { status: string }) => {
      expect(tx.status).toBe("APPROVED");
    });
  });

  it("GET /api/transactions — requires auth", async () => {
    const res = await request(app).get("/api/transactions");
    expect(res.status).toBe(401);
  });

  it("POST /api/transactions — invalid wallet returns 400", async () => {
    const res = await request(app)
      .post("/api/transactions")
      .set("Authorization", `Bearer ${token}`)
      .send({
        fromWallet: "not-a-wallet",
        toWallet: "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        amount: 100,
        currency: "USD",
      });
    expect(res.status).toBe(400);
  });

  it("GET /api/dashboard/stats — returns real stats", async () => {
    const res = await request(app)
      .get("/api/dashboard/stats")
      .set("Authorization", `Bearer ${token}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(typeof res.body.data.totalTransactions).toBe("number");
    expect(Array.isArray(res.body.data.dailyVolume)).toBe(true);
  });
});
