#!/bin/bash

# Live Audio Stream Server - Quick Start Script

echo "=========================================="
echo "Live Audio Streaming Server - Quick Start"
echo "=========================================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install/update requirements
echo "Installing requirements..."
pip install -q -r requirements.txt

echo ""
echo "Starting server..."
echo ""

# Run the server
python stream_server.py
