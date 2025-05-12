from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
import os
import uuid
import requests
import folium
import datetime
from werkzeug.utils import secure_filename
from PIL import Image
import io
import json
import google.generativeai as genai
from folium.plugins import MarkerCluster

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-key-for-dev')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  
app.config['CONTENT_FILE'] = 'static/content/site_content.json'

# Ensure necessary directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/content', exist_ok=True)
os.makedirs('static/maps', exist_ok=True)

# Set API keys - in production, use environment variables
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', 'your-gemini-api-key')
GEOAPIFY_API_KEY = os.environ.get('GEOAPIFY_API_KEY', 'your-geoapify-api-key')

# Configure Gemini AI
genai.configure(api_key=GEMINI_API_KEY)

# Create the Gemini AI model with specific configuration
generation_config = {
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 4096,
}
model = genai.GenerativeModel(
    model_name="gemini-1.5-pro",
    generation_config=generation_config,
)

# Define the system prompt for skin analysis
skin_analysis_prompt = """
As a highly skilled dermatologist specializing in skin analysis, you are tasked with analyzing a person's skin type and recommending appropriate skincare products. Your expertise is crucial in identifying skin concerns and providing personalized recommendations.

Your Responsibilities:
1. Analyze the image and identify the skin type (dry, oily, combination, normal, sensitive).
2. Identify key skin concerns (acne, aging, hyperpigmentation, redness, etc.).
3. Recommend 3 specific product types with their benefits for this skin type.
4. For each product, suggest specific ingredients that would be beneficial.

Important Notes:
1. Only respond if the image pertains to human skin.
2. If the image quality impedes clear analysis, note that certain aspects are "Unable to determine based on the provided image."
3. Format your response as structured JSON with the following fields:
   {
     "skin_type": "",
     "concerns": ["", "", ""],  
     "products": [
       {"type": "", "purpose": "", "key_ingredients": [], "usage": "", "benefit": ""},
       {"type": "", "purpose": "", "key_ingredients": [], "usage": "", "benefit": ""},
       {"type": "", "purpose": "", "key_ingredients": [], "usage": "", "benefit": ""}
     ],
     "general_tips": ["", "", ""]
   }

Always accompany your analysis with the disclaimer: "This analysis is for informational purposes only. Please consult with a dermatologist for a professional diagnosis."
"""

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Function to get nearby stores using Geoapify API
def get_nearby_stores(lat, lon, radius=5000, limit=5):
    url = f"https://api.geoapify.com/v2/places?categories=commercial.beauty,commercial.cosmetics,commercial.health_and_beauty,commercial.pharmacy&filter=circle:{lon},{lat},{radius}&limit={limit}&apiKey={GEOAPIFY_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data['features']
    return []

# Function to create a map with user location and nearby stores
def create_map(user_lat, user_lon, stores):
    m = folium.Map(location=[user_lat, user_lon], zoom_start=13)
    
    # Add user marker
    folium.Marker(
        [user_lat, user_lon],
        popup="Your Location",
        icon=folium.Icon(color="red", icon="home")
    ).add_to(m)
    
    # Add store markers with cluster
    marker_cluster = MarkerCluster().add_to(m)
    
    for store in stores:
        properties = store['properties']
        lat = properties.get('lat')
        lon = properties.get('lon')
        
        if lat and lon:
            folium.Marker(
                [lat, lon],
                popup=f"<b>{properties.get('name', 'Store')}</b><br>{properties.get('address_line2', 'No address')}",
                icon=folium.Icon(color="blue", icon="shopping-bag", prefix='fa')
            ).add_to(marker_cluster)
    
    # Save map to file
    map_file = f"static/maps/map_{uuid.uuid4().hex}.html"
    m.save(os.path.join(app.root_path, map_file))
    
    return map_file

@app.route("/")
def index():
    return render_template("skincare_index.html", current_year=datetime.datetime.now().year)

@app.route("/analyze", methods=['GET', 'POST'])
def analyze():
    if request.method == 'POST':
        # Check if the post request has the file part
        if 'skin_image' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
        
        file = request.files['skin_image']
        
        # If user does not select file, browser also submits an empty part without filename
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            # Generate a unique filename to prevent overwriting
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            
            # Get location data if provided
            user_lat = request.form.get('latitude', type=float)
            user_lon = request.form.get('longitude', type=float)
            
            # Process image with Gemini AI
            try:
                with open(file_path, "rb") as img_file:
                    image_data = img_file.read()
                
                image_parts = [
                    {
                        "mime_type": f"image/{file_path.split('.')[-1]}",
                        "data": image_data
                    }
                ]
                
                prompt_parts = [
                    image_parts[0],
                    skin_analysis_prompt,
                ]
                
                response = model.generate_content(prompt_parts)
                analysis_result = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
                
                # Store results in session
                session['analysis_result'] = analysis_result
                session['image_path'] = os.path.join('uploads', unique_filename)
                
                # Create map if location is provided
                map_file = None
                nearby_stores = []
                
                if user_lat and user_lon:
                    stores = get_nearby_stores(user_lat, user_lon)
                    if stores:
                        map_file = create_map(user_lat, user_lon, stores)
                        
                        # Process store data for template
                        for store in stores:
                            props = store['properties']
                            nearby_stores.append({
                                'name': props.get('name', 'Unnamed Store'),
                                'address': props.get('address_line2', 'No address available'),
                                'distance': f"{(props.get('distance', 1000) / 1000):.1f} km",
                                'coordinates': {
                                    'lat': props.get('lat'),
                                    'lng': props.get('lon')
                                }
                            })
                
                session['map_file'] = map_file
                session['nearby_stores'] = nearby_stores
                
                return redirect(url_for('results'))
                
            except Exception as e:
                print(f"Error analyzing image: {e}")
                flash(f"Error analyzing image: {str(e)}", 'error')
                return redirect(request.url)
        else:
            flash('File type not allowed', 'error')
            return redirect(request.url)
    
    return render_template("skincare_analyze.html", current_year=datetime.datetime.now().year)

@app.route("/results")
def results():
    # Check if we have results in the session
    if 'analysis_result' not in session or 'image_path' not in session:
        flash('No analysis results found. Please upload an image first.', 'error')
        return redirect(url_for('analyze'))
    
    results = {
        'analysis': session['analysis_result'],
        'image_path': session['image_path'],
        'map_file': session.get('map_file'),
        'nearby_stores': session.get('nearby_stores', [])
    }
    
    return render_template("skincare_results.html", results=results, current_year=datetime.datetime.now().year)

@app.route("/about")
def about():
    return render_template("skincare_about.html", current_year=datetime.datetime.now().year)

if __name__ == '__main__':
    app.run(debug=True, port=5000) 