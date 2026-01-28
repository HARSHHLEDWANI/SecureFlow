#!/usr/bin/env node
require('ts-node/register');
const app = require('./src/app').default;

const PORT = process.env.PORT || 3001;

app.listen(PORT, () => {
  console.log(`✅ Backend running on http://localhost:${PORT}`);
  console.log(`📍 API endpoints available at http://localhost:${PORT}/api`);
});
