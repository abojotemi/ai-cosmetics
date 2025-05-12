# SkinCare AI - Personalized Skin Analysis and Product Recommendations

SkinCare AI is a Flask application that uses Google's Gemini AI to analyze skin types from uploaded photos, recommend skincare products, and show nearby stores where these products can be purchased.

## Features

- **AI Skin Analysis**: Upload a photo and get personalized skin type analysis
- **Product Recommendations**: Receive tailored product recommendations for your skin type
- **Nearby Store Mapping**: Find stores near you that carry recommended products
- **Interactive Maps**: View store locations on interactive maps

## Technology Stack

- **Backend**: Flask (Python)
- **Frontend**: Tailwind CSS, HTML, JavaScript
- **AI**: Google Gemini AI for image analysis
- **Mapping**: Folium for interactive maps
- **Location Data**: Geoapify API for nearby store information

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd tailwind-flask-starter
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install the dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up API keys:
   
   Create a `.env` file in the project root with your API keys:
   ```
   GEMINI_API_KEY=your-gemini-api-key
   GEOAPIFY_API_KEY=your-geoapify-api-key
   ```

   You'll need to sign up for:
   - [Google AI Studio](https://ai.google.dev/) for Gemini API key
   - [Geoapify](https://www.geoapify.com/) for location API key

## Running the Application

Run the application using the provided script:
```
bash run_skincare_app.sh
```

Or run it directly with Python:
```
python skincare_app.py
```

The application will be available at http://localhost:5000/

## Usage

1. Visit the homepage at http://localhost:5000/
2. Click on "Analyze My Skin" to go to the analysis page
3. Upload a clear photo of your face or skin area
4. Optionally share your location to find nearby stores
5. Review your skin analysis results and product recommendations
6. Explore the map to find nearby stores that carry your recommended products

## File Structure

- `skincare_app.py`: Main Flask application with routes and logic
- `templates/`: HTML templates for the web interface
  - `skincare_index.html`: Homepage
  - `skincare_analyze.html`: Photo upload and analysis page
  - `skincare_results.html`: Results page with product recommendations and map
  - `skincare_about.html`: About page with information about the app
- `static/`: Static files (CSS, JavaScript, uploaded images)
  - `uploads/`: Folder for uploaded skin images
  - `maps/`: Folder for generated map files

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE.md file for details. 