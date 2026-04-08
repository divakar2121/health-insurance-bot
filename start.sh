#!/bin/bash
# Startup script for Health Insurance AI Bot

echo "Starting Health Insurance AI Bot..."
echo "Activating conda environment 'ai'..."
source /home/deva/miniconda3/etc/profile.d/conda.sh && conda activate ai

echo "Starting Flask application..."
python app.py

echo "Health Insurance AI Bot is running at http://localhost:5001"