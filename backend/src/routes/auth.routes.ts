import { Router, Request, Response, NextFunction } from "express";
const jwt = require("jsonwebtoken");
const bcrypt = require("bcryptjs");

const router = Router();

const JWT_SECRET = process.env.JWT_SECRET || "dev_secret";

type User = {
  id: string;
  email: string;
  passwordHash: string;
  name?: string;
};

// In-memory user store for demo purposes
const users: User[] = [];

function generateToken(user: User) {
  return jwt.sign({ sub: user.id, email: user.email }, JWT_SECRET, {
    expiresIn: "7d",
  });
}

function hashPassword(plain: string) {
  return bcrypt.hashSync(plain, 10);
}

function authMiddleware(req: Request, res: Response, next: NextFunction) {
  const auth = req.headers.authorization?.split(" ")[1];
  if (!auth) return res.status(401).json({ error: "Missing authorization" });
  try {
    const payload = jwt.verify(auth, JWT_SECRET) as any;
    // attach to request
    (req as any).auth = payload;
    next();
  } catch (err) {
    return res.status(401).json({ error: "Invalid token" });
  }
}

router.post("/signup", (req, res) => {
  const { email, password, name } = req.body;
  if (!email || !password) return res.status(400).json({ error: "Missing email or password" });

  const exists = users.find((u) => u.email.toLowerCase() === email.toLowerCase());
  if (exists) return res.status(409).json({ error: "User already exists" });

  const passwordHash = hashPassword(password);
  const user: User = { id: `user-${Date.now()}`, email, passwordHash, name };
  users.push(user);

  const token = generateToken(user);

  res.json({ token, user: { id: user.id, email: user.email, name: user.name } });
});

router.post("/login", (req, res) => {
  const { email, password } = req.body;
  if (!email || !password) return res.status(400).json({ error: "Missing email or password" });

  const user = users.find((u) => u.email.toLowerCase() === email.toLowerCase());
  if (!user) return res.status(401).json({ error: "Invalid credentials" });

  const ok = bcrypt.compareSync(password, user.passwordHash);
  if (!ok) return res.status(401).json({ error: "Invalid credentials" });

  const token = generateToken(user);
  res.json({ token, user: { id: user.id, email: user.email, name: user.name } });
});

router.get("/me", authMiddleware, (req, res) => {
  const auth = (req as any).auth as any;
  const user = users.find((u) => u.id === auth.sub);
  if (!user) return res.status(404).json({ error: "User not found" });
  res.json({ id: user.id, email: user.email, name: user.name });
});

export default router;
