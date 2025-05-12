#!/bin/bash

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    echo "Loading environment variables from .env file"
    export $(grep -v '^#' .env | xargs)
fi

# Set default API keys if not provided in environment
if [ -z "$GEMINI_API_KEY" ]; then
    echo "Warning: GEMINI_API_KEY not set. Using default placeholder value."
    export GEMINI_API_KEY="your-gemini-api-key"
fi

if [ -z "$GEOAPIFY_API_KEY" ]; then
    echo "Warning: GEOAPIFY_API_KEY not set. Using default placeholder value."
    export GEOAPIFY_API_KEY="your-geoapify-api-key"
fi

# Run the application
echo "Starting SkinCare AI application..."
python skincare_app.py 