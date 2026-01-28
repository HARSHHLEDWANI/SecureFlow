# SecureFlow API Endpoints Reference

## Base URL
```
http://localhost:3001/api
```

## Transactions
```
GET /api/transactions
Query params: ?skip=0&take=100&status=APPROVED

POST /api/transactions
Body: {
  fromWallet: string
  toWallet: string
  amount: number
  currency: string
}

GET /api/transactions/:id
```

## Audit
```
GET /api/audit
Query params: ?skip=0&take=100&status=success

GET /api/audit/stats
Response: {
  totalAudited: number
  successRate: number
  averageLatency: number
}
```

## Settings
```
GET /api/settings
Response: {
  id: string
  email: string
  riskThreshold: number
  notificationsEnabled: boolean
  twoFactorEnabled: boolean
  apiKeys: string[]
  createdAt: string
  updatedAt: string
}

PUT /api/settings
Body: Partial<UserSettings>

POST /api/settings/api-keys
Response: {
  key: string
  createdAt: string
}
```

## Dashboard
```
GET /api/dashboard/stats
Response: {
  totalTransactions: number
  flaggedTransactions: number
  averageRiskScore: number
  totalAudited: number
}
```

## Frontend Configuration
Set `NEXT_PUBLIC_BACKEND_URL=http://localhost:3001/api` in `.env.local`

All API calls are handled through `/frontend/src/lib/api.ts`
