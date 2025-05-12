#!/bin/bash

# Create a Python virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
fi

# Activate the virtual environment
source .venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Install Node.js dependencies for Tailwind CSS
echo "Installing Node.js dependencies..."
npm install

# Build Tailwind CSS
echo "Building Tailwind CSS..."
npm run build

# Initialize the database with a test user
echo "Initializing database..."
python init_db.py

# Create necessary directories if they don't exist
mkdir -p static/uploads
mkdir -p static/maps
mkdir -p static/content

echo ""
echo "Setup complete! You can now run the application with:"
echo "python app.py"
echo ""
echo "Test user credentials:"
echo "Email: test@example.com"
echo "Password: password123" 