#!/bin/bash
# SecureFlow - Launch Script

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}SecureFlow - Payment Fraud Detection System${NC}"
echo ""

show_help() {
    echo -e "${YELLOW}Prerequisites:${NC}"
    echo "  - Node.js >= 18"
    echo "  - Python >= 3.11"
    echo "  - PostgreSQL 16 running on port 5432"
    echo ""
    echo -e "${YELLOW}Manual Setup (3 terminals):${NC}"
    echo ""
    echo "Terminal 1 - Backend:"
    echo -e "  ${BLUE}cd backend && npm install${NC}"
    echo -e "  ${BLUE}npx prisma migrate dev && npx prisma db seed${NC}"
    echo -e "  ${BLUE}npm run dev${NC}  → http://localhost:4000"
    echo ""
    echo "Terminal 2 - AI Service:"
    echo -e "  ${BLUE}cd ai-service && python -m venv venv${NC}"
    echo -e "  ${BLUE}source venv/bin/activate${NC}"
    echo -e "  ${BLUE}pip install -r requirements.txt${NC}"
    echo -e "  ${BLUE}python app/train.py${NC}"
    echo -e "  ${BLUE}uvicorn app.main:app --reload --port 8000${NC}  → http://localhost:8000"
    echo ""
    echo "Terminal 3 - Frontend:"
    echo -e "  ${BLUE}cd frontend && npm install${NC}"
    echo -e "  ${BLUE}cp .env.local.example .env.local${NC}"
    echo -e "  ${BLUE}npm run dev${NC}  → http://localhost:3000"
    echo ""
    echo -e "${YELLOW}Docker Setup:${NC}"
    echo -e "  ${BLUE}docker compose up --build${NC}"
    echo ""
    echo -e "${YELLOW}API Endpoints (backend port 4000):${NC}"
    echo "  POST /api/auth/login"
    echo "  GET  /api/dashboard/stats"
    echo "  GET  /api/transactions"
    echo "  POST /api/transactions"
    echo "  GET  /api/audit"
    echo "  GET  /api/settings"
    echo ""
    echo -e "${YELLOW}Troubleshooting:${NC}"
    echo "  Port 4000 in use: lsof -i :4000 | awk 'NR>1{print \$2}' | xargs kill -9"
    echo "  Port 3000 in use: lsof -i :3000 | awk 'NR>1{print \$2}' | xargs kill -9"
    echo "  Backend health:   curl http://localhost:4000/api/health"
}

show_help

if [ "$1" == "--auto" ]; then
    echo -e "${YELLOW}Starting all services...${NC}"
    echo ""

    cd backend
    npm install --silent
    npm run dev &
    BACKEND_PID=$!
    echo -e "${GREEN}Backend started (PID: $BACKEND_PID) → http://localhost:4000${NC}"
    sleep 2
    cd ..

    cd ai-service
    if [ ! -d "venv" ]; then
        python -m venv venv
    fi
    source venv/bin/activate 2>/dev/null || source venv/Scripts/activate
    pip install -r requirements.txt --quiet
    if [ ! -f "models/fraud_model.joblib" ]; then
        python app/train.py
    fi
    uvicorn app.main:app --port 8000 &
    AI_PID=$!
    echo -e "${GREEN}AI Service started (PID: $AI_PID) → http://localhost:8000${NC}"
    sleep 2
    cd ..

    cd frontend
    npm install --silent
    npm run dev &
    FRONTEND_PID=$!
    echo -e "${GREEN}Frontend started (PID: $FRONTEND_PID) → http://localhost:3000${NC}"
    cd ..

    echo ""
    echo -e "${GREEN}All services running. Press Ctrl+C to stop.${NC}"

    trap "kill $BACKEND_PID $AI_PID $FRONTEND_PID 2>/dev/null; echo 'Services stopped.'" EXIT
    wait
fi
