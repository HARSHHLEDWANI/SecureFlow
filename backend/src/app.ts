import express from "express";
import cors from "cors";
import transactionRoutes from "./routes/transaction.routes";
import { errorHandler } from "./middleware/error.middleware";

const app = express();

app.use(cors());
app.use(express.json());

app.use("/transactions", transactionRoutes);

app.use(errorHandler);

export default app;
