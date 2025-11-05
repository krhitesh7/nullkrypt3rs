#!/bin/bash

# Start NullKrypt3rs GitHub Webhook Server

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}NullKrypt3rs Webhook Server${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if .env file exists
if [ ! -f "httpapi/.env" ]; then
    echo -e "${YELLOW}Warning: .env file not found${NC}"
    echo -e "${YELLOW}Creating from .env.example...${NC}"
    
    if [ -f "httpapi/.env.example" ]; then
        cp httpapi/.env.example httpapi/.env
        echo -e "${RED}Please edit httpapi/.env with your credentials before running again${NC}"
        exit 1
    else
        echo -e "${RED}Error: .env.example not found${NC}"
        exit 1
    fi
fi

# Load environment variables
echo -e "${GREEN}Loading environment variables...${NC}"
export $(cat httpapi/.env | grep -v '^#' | xargs)

# Check required environment variables
if [ -z "$GITHUB_TOKEN" ]; then
    echo -e "${RED}Error: GITHUB_TOKEN not set in .env${NC}"
    exit 1
fi

if [ -z "$GITHUB_WEBHOOK_SECRET" ]; then
    echo -e "${YELLOW}Warning: GITHUB_WEBHOOK_SECRET not set - signature validation disabled${NC}"
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo -e "${GREEN}Activating virtual environment...${NC}"
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo -e "${GREEN}Activating virtual environment...${NC}"
    source .venv/bin/activate
fi

# Check if Flask is installed
if ! python -c "import flask" 2>/dev/null; then
    echo -e "${RED}Error: Flask not installed${NC}"
    echo -e "${YELLOW}Run: pip install -r requirements.txt${NC}"
    exit 1
fi

# Start the server
echo -e "${GREEN}Starting webhook server...${NC}"
python httpapi/server.py

