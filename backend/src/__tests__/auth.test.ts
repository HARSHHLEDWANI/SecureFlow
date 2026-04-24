import request from "supertest";
import app from "../app";

describe("Auth endpoints", () => {
  let accessToken: string;
  let refreshToken: string;

  it("POST /api/auth/login — valid credentials returns token", async () => {
    const res = await request(app).post("/api/auth/login").send({
      email: "admin@secureflow.dev",
      password: "SecureFlow123!",
    });
    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.data.accessToken).toBeDefined();
    accessToken = res.body.data.accessToken;
    refreshToken = res.headers["set-cookie"]?.[0]?.match(/refreshToken=([^;]+)/)?.[1] ?? "";
  });

  it("POST /api/auth/login — wrong password returns 401", async () => {
    const res = await request(app).post("/api/auth/login").send({
      email: "admin@secureflow.dev",
      password: "wrongpassword",
    });
    expect(res.status).toBe(401);
    expect(res.body.success).toBe(false);
  });

  it("POST /api/auth/login — missing fields returns 400", async () => {
    const res = await request(app).post("/api/auth/login").send({ email: "test@test.com" });
    expect(res.status).toBe(400);
  });

  it("GET /api/auth/me — valid token returns user", async () => {
    const loginRes = await request(app).post("/api/auth/login").send({
      email: "admin@secureflow.dev",
      password: "SecureFlow123!",
    });
    const token = loginRes.body.data.accessToken;

    const res = await request(app)
      .get("/api/auth/me")
      .set("Authorization", `Bearer ${token}`);

    expect(res.status).toBe(200);
    expect(res.body.data.email).toBe("admin@secureflow.dev");
  });

  it("GET /api/auth/me — no token returns 401", async () => {
    const res = await request(app).get("/api/auth/me");
    expect(res.status).toBe(401);
  });
});
