#!/bin/bash

# Create content directory if it doesn't exist
mkdir -p static/content
mkdir -p static/uploads

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing npm dependencies..."
    npm install
fi

if [ ! -d ".venv/lib" ]; then
    echo "Installing Python dependencies..."
    pip install -r requirements.txt
fi

# Set dev environment variables
export FLASK_ENV=development
export FLASK_DEBUG=1
# Default admin password - change this in production!
export ADMIN_PASSWORD=admin

# Start TailwindCSS in watch mode
echo "Starting TailwindCSS watch process..."
npm run dev &
TAILWIND_PID=$!

# Start Flask app
echo "Starting Flask application..."
python app.py

# Kill TailwindCSS process when Flask is stopped
kill $TAILWIND_PID 