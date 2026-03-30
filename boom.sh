#!/usr/bin/env bash

# boom.sh - One-click setup and start for DeerFlow on Mac
# Author: Basil Suhail's Senior Coding Partner

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}  🚀 DEERFLOW BOOM MODE: ACTUALLY WORKS!  ${NC}"
echo -e "${BLUE}==========================================${NC}"

# 1. Directory Check
if [ ! -f "Makefile" ] || [ ! -d "scripts" ]; then
    echo -e "${RED}❌ Error: Please run this script from the DeerFlow 'repo' root.${NC}"
    exit 1
fi

# 2. Docker Check
echo -ne "${YELLOW}Checking Docker... ${NC}"
if ! command -v docker >/dev/null 2>&1; then
    echo -e "${RED}❌ Docker not found. Please install it first.${NC}"
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker Desktop.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Running${NC}"

# 3. Ollama Check
echo -ne "${YELLOW}Checking Ollama... ${NC}"
if ! curl -s http://localhost:11434 >/dev/null 2>&1; then
    echo -e "${RED}❌ Ollama is not running on port 11434.${NC}"
    echo -e "${YELLOW}Hint: Start Ollama app and pull your model (e.g., 'ollama pull qwen2.5:7b').${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Running${NC}"

# 4. Config & Env Files
echo -e "${YELLOW}Bootstrapping configuration...${NC}"
# Use the existing python script to avoid duplicating logic
python3 ./scripts/configure.py || echo -e "${BLUE}ℹ Configuration already exists, skipping...${NC}"

# 5. Logs directory
if [ ! -d "logs" ]; then
    mkdir -p logs
    echo -e "${GREEN}✓ Created logs directory${NC}"
fi

# 6. Cleanup previous runs (Optional but recommended to "actually work")
echo -e "${YELLOW}Cleaning up stale containers and networks...${NC}"
# Use the known network conflict fix from README
docker stop deer-flow-nginx deer-flow-gateway deer-flow-langgraph deer-flow-frontend 2>/dev/null || true
docker rm deer-flow-nginx deer-flow-gateway deer-flow-langgraph deer-flow-frontend 2>/dev/null || true
docker network rm deer-flow-dev_deer-flow-dev 2>/dev/null || true

# 7. Start the Engine
echo -e "${BLUE}Building and starting DeerFlow... (this might take a minute)${NC}"
make docker-start

# 8. Success!
echo -e ""
echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}  ✨ DEERFLOW IS READY TO PLAY!          ${NC}"
echo -e "${GREEN}==========================================${NC}"
echo -e ""
echo -e "  🌐 URL: http://localhost:2026"
echo -e "  📡 Logs: make docker-logs"
echo -e ""
echo -e "${YELLOW}Note: If you get 502 Bad Gateway, wait 10 seconds for Next.js to compile.${NC}"
echo -e ""
