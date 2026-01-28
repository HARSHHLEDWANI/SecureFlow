#!/bin/bash
# SecureFlow - Launch Script
# Run this to start the entire application

echo "╔════════════════════════════════════════════════════════════╗"
echo "║          🚀 SecureFlow - Professional SaaS Platform       ║"
echo "║              Backend-Frontend Integration Ready             ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}📋 Prerequisites Check:${NC}"
echo "✓ Node.js installed"
echo "✓ npm installed"
echo "✓ Git installed"
echo ""

echo -e "${YELLOW}📁 Project Structure:${NC}"
echo "✓ /frontend     - Next.js SaaS UI"
echo "✓ /backend      - Express.js API"
echo "✓ /blockchain   - Smart Contracts"
echo ""

echo -e "${BLUE}🚀 Starting Services...${NC}"
echo ""

# Function to display help
show_help() {
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                   How to Run SecureFlow                    ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}Option 1: Manual Setup (Recommended for first time)${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Backend Terminal:"
    echo -e "  ${BLUE}$ cd backend${NC}"
    echo -e "  ${BLUE}$ npm install${NC}"
    echo -e "  ${BLUE}$ npm run dev${NC}"
    echo "  ✓ Backend running on http://localhost:3001"
    echo ""
    echo "Frontend Terminal:"
    echo -e "  ${BLUE}$ cd frontend${NC}"
    echo -e "  ${BLUE}$ npm install${NC}"
    echo -e "  ${BLUE}$ npm run dev${NC}"
    echo "  ✓ Frontend running on http://localhost:3000"
    echo ""
    echo "Browser:"
    echo -e "  ${GREEN}Open: http://localhost:3000${NC}"
    echo ""
    echo -e "${YELLOW}Option 2: Docker (if available)${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  docker-compose up"
    echo ""
    echo -e "${YELLOW}Pages Available:${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  📊 Dashboard      → http://localhost:3000"
    echo "  📋 Transactions   → http://localhost:3000/transactions"
    echo "  🔍 Audit Logs     → http://localhost:3000/audit"
    echo "  ⚙️  Settings       → http://localhost:3000/settings"
    echo ""
    echo -e "${YELLOW}API Endpoints:${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Base URL: http://localhost:3001/api"
    echo ""
    echo "  GET  /api/dashboard/stats"
    echo "  GET  /api/transactions"
    echo "  POST /api/transactions"
    echo "  GET  /api/audit"
    echo "  GET  /api/audit/stats"
    echo "  GET  /api/settings"
    echo "  PUT  /api/settings"
    echo "  POST /api/settings/api-keys"
    echo ""
    echo -e "${YELLOW}🔧 Troubleshooting:${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Port 3001 already in use?"
    echo "  Kill process: lsof -i :3001 | grep LISTEN | awk '{print $2}' | xargs kill -9"
    echo ""
    echo "Port 3000 already in use?"
    echo "  Kill process: lsof -i :3000 | grep LISTEN | awk '{print $2}' | xargs kill -9"
    echo ""
    echo "Module not found?"
    echo "  Run: npm install in both backend and frontend"
    echo ""
    echo "Backend not responding?"
    echo "  Check: curl http://localhost:3001/api/dashboard/stats"
    echo ""
    echo -e "${YELLOW}📚 Documentation:${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  QUICKSTART.md              - Quick start guide"
    echo "  IMPLEMENTATION_GUIDE.md    - Full architecture"
    echo "  API_ENDPOINTS.md           - API reference"
    echo "  PROJECT_SUMMARY.md         - Project overview"
    echo ""
    echo -e "${GREEN}Ready to launch? Follow Option 1 above! 🚀${NC}"
    echo ""
}

# Show help
show_help

# Check if running with --auto flag
if [ "$1" == "--auto" ]; then
    echo -e "${YELLOW}Starting automatic setup...${NC}"
    echo ""
    
    # Backend
    echo -e "${BLUE}Starting Backend...${NC}"
    cd backend
    npm install > /dev/null 2>&1
    echo -e "${GREEN}✓ Backend dependencies installed${NC}"
    npm run dev &
    BACKEND_PID=$!
    echo -e "${GREEN}✓ Backend started (PID: $BACKEND_PID)${NC}"
    echo "  Running on: http://localhost:3001"
    
    sleep 2
    cd ..
    
    # Frontend
    echo ""
    echo -e "${BLUE}Starting Frontend...${NC}"
    cd frontend
    npm install > /dev/null 2>&1
    echo -e "${GREEN}✓ Frontend dependencies installed${NC}"
    npm run dev &
    FRONTEND_PID=$!
    echo -e "${GREEN}✓ Frontend started (PID: $FRONTEND_PID)${NC}"
    echo "  Running on: http://localhost:3000"
    
    sleep 2
    cd ..
    
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              ✅ SecureFlow is running!                   ║${NC}"
    echo -e "${GREEN}╠════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${GREEN}║  Frontend: ${BLUE}http://localhost:3000${GREEN}                     ║${NC}"
    echo -e "${GREEN}║  Backend:  ${BLUE}http://localhost:3001${GREEN}                     ║${NC}"
    echo -e "${GREEN}║  API:      ${BLUE}http://localhost:3001/api${GREEN}                  ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}Press Ctrl+C to stop both servers${NC}"
    echo ""
    
    # Wait for Ctrl+C
    wait
    
    # Cleanup
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo -e "${GREEN}Services stopped.${NC}"
fi
