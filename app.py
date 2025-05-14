from pprint import pprint
from typing import Literal
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
)
import os
import time
import uuid
import json
from pydantic import BaseModel, Field
import requests
import folium
import datetime
from werkzeug.utils import secure_filename
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)

from google import genai
from google.genai import types
from google.genai.errors import ServerError, APIError

# from folium.plugins import MarkerCluster
from dotenv import load_dotenv

# Import User model from models
from models.user import db, User
from models.analysis import Analysis


# Helper function to determine store type from categories
def get_store_type(categories):
    # Handle both string and list input
    if isinstance(categories, str):
        categories_list = [categories]
    else:
        categories_list = categories
        
    if any("cosmetics" in cat for cat in categories_list):
        return "Cosmetics Store"
    elif any("pharmacy" in cat for cat in categories_list):
        return "Pharmacy"
    elif any("health_and_beauty" in cat for cat in categories_list):
        return "Beauty Shop"
    elif any("chemist" in cat for cat in categories_list):
        return "Chemist"
    elif any("department_store" in cat for cat in categories_list):
        return "Department Store"
    elif any("shopping_mall" in cat for cat in categories_list):
        return "Shopping Mall"
    elif any("supermarket" in cat for cat in categories_list):
        return "Supermarket"
    else:
        return "Store"


load_dotenv()
app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "static/uploads"
app.config["ALLOWED_EXTENSIONS"] = {"png", "jpg", "jpeg"}
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "default-key-for-dev")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
app.config["CONTENT_FILE"] = "static/content/site_content.json"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///site.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize SQLAlchemy and Flask-Login
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message_category = "error"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Ensure necessary directories exist
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs("static/content", exist_ok=True)
os.makedirs("static/maps", exist_ok=True)

# Set API keys - in production, use environment variables
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "your-gemini-api-key")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
GEOAPIFY_API_KEY = os.environ.get("GEOAPIFY_API_KEY", "your-geoapify-api-key")


# Create the Gemini AI model with specific configuration

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
3. If the image is not human skin, fill all available result fields with "Not Human Skin"


Always accompany your analysis with the disclaimer: "This analysis is for informational purposes only. Please consult with a dermatologist for a professional diagnosis."
"""


class Products(BaseModel):
    type: str = Field(description="Recommend a specific product type")
    purpose: str = Field(
        description="Explain the purpose of this product for this skin type"
    )
    key_ingredients: list[str] = Field(
        description="List the key ingredients found in this product"
    )
    usage: str = Field(description="Describe the way the product should be used")
    benefit: str = Field(
        description="Explain the benefits of this product for the specific skin type"
    )


class Skin(BaseModel):
    skin_type: Literal["oily", "sensitive", "dry", "normal", "not skin"] = Field(
        description="Analyze the image and identify the skin type (dry, oily, normal, sensitive)."
    )
    concerns: list[str] = Field(
        description="Identify key skin concerns (acne, aging, hyperpigmentation, redness, etc.)."
    )
    products: list[Products] = Field(
        description="Recommend 3 specific products suitable for the user"
    )
    general_tips: list[str] = Field(description="Give tips to improve the user's skin.")


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]
    )


# Function to get nearby stores using Geoapify API
def get_nearby_stores(lat, lon, radius=5000, limit=10):
    try:
        # Use valid categories supported by Geoapify API
        categories = [
            "commercial.health_and_beauty.cosmetics",
            "commercial.health_and_beauty.pharmacy",
            "commercial.health_and_beauty",
            "commercial.chemist",
            "commercial.department_store",
            "commercial.shopping_mall",
            "commercial.supermarket",
        ]
        
        categories_str = ",".join(categories)
        url = f"https://api.geoapify.com/v2/places?categories={categories_str}&filter=circle:{lon},{lat},{radius}&limit={limit}&apiKey={GEOAPIFY_API_KEY}"
        
        print(f"Requesting URL: {url}")
        print(
            f"Using Geoapify API key: {GEOAPIFY_API_KEY[:5]}...{GEOAPIFY_API_KEY[-5:] if len(GEOAPIFY_API_KEY) > 10 else ''}"
        )
        
        response = requests.get(url, timeout=10)  # Add timeout to prevent hanging
        response.raise_for_status()  # Raise an exception for bad status codes

        data = response.json()
        features = data.get("features", [])

        # Print the number of features found
        features_count = len(features)
        print(f"Found {features_count} stores nearby")
        
        if features_count > 0:
            first_store = features[0]
            print("Sample store data:")
            print(f"  Name: {first_store['properties'].get('name', 'No name')}")
            print(
                f"  Categories: {first_store['properties'].get('categories', 'No categories')}"
            )
            print(
                f"  Address: {first_store['properties'].get('formatted', 'No address')}"
            )

            return features
        else:
            print("No stores found with Geoapify API, falling back to mock data")
            return get_mock_stores(lat, lon, radius)

    except requests.exceptions.RequestException as e:
        print(f"Error fetching stores from API: {e}")
        print("Falling back to mock data due to API error")
        return get_mock_stores(lat, lon, radius)
    except Exception as e:
        print(f"Unexpected error in get_nearby_stores: {e}")
        print("Falling back to mock data due to unexpected error")
        return get_mock_stores(lat, lon, radius)


# Function to generate mock store data for demonstration
def get_mock_stores(lat, lon, radius=5000, count=5):
    """Generate mock store data when API fails"""
    import random
    from math import cos, sin, pi, sqrt
    
    mock_stores = []
    store_types = [
        {"name": "Beauty Paradise", "type": "commercial.health_and_beauty.cosmetics"},
        {"name": "Pharmacia", "type": "commercial.health_and_beauty.pharmacy"},
        {"name": "Skin Essentials", "type": "commercial.health_and_beauty"},
        {"name": "ChemCare", "type": "commercial.chemist"},
        {"name": "Nordstrom", "type": "commercial.department_store"},
        {"name": "Fashion Center Mall", "type": "commercial.shopping_mall"},
        {"name": "SuperMarket Plus", "type": "commercial.supermarket"},
    ]
    
    radius_km = radius / 1000
    
    for i in range(count):
        # Generate a random point within the radius
        r = radius_km * sqrt(random.random())
        theta = random.random() * 2 * pi
        
        # Convert to lat/lon offset (approximate)
        dx = r * cos(theta)
        dy = r * sin(theta)
        
        # 111,111 meters is roughly 1 degree of latitude
        # Longitude degrees vary based on latitude
        lat_offset = dy / 111.111
        lon_offset = dx / (111.111 * cos(lat * pi / 180))
        
        store_lat = lat + lat_offset
        store_lon = lon + lon_offset
        
        # Pick a random store type
        store_info = random.choice(store_types)
        
        # Calculate distance in meters
        distance = r * 1000
        
        mock_store = {
            "properties": {
                "name": f"{store_info['name']} #{i+1}",
                "categories": store_info["type"],
                "street": "Main Street",
                "housenumber": str(random.randint(1, 100)),
                "city": "Your City",
                "lat": store_lat,
                "lon": store_lon,
                "distance": distance,
                "formatted": f"{random.randint(1, 100)} Main Street, Your City",
            },
            "geometry": {"coordinates": [store_lon, store_lat]},
            "is_mock": True,
        }
        mock_stores.append(mock_store)
    
    print(f"Generated {count} mock stores for demonstration")
    return mock_stores


# Function to create a map with user location and nearby stores
def create_map(user_lat, user_lon, stores, radius=5000):
    # Create a basic map centered at the user's location
    m = folium.Map(location=[user_lat, user_lon], zoom_start=13)

    # Add user location marker
    folium.Marker(
        [user_lat, user_lon],
        popup="Your Location",
        icon=folium.Icon(color="red", icon="info-sign"),
    ).add_to(m)

    # Add search radius circle
    folium.Circle(
        [user_lat, user_lon],
        radius=radius,
        color="blue",
        fill=True,
        fill_color="blue",
        fill_opacity=0.1,
        popup=f"Search Radius: {radius/1000:.1f}km",
    ).add_to(m)

    # Add store markers if available
    if stores:
        for store in stores:
            store_lat = store["geometry"]["coordinates"][1]
            store_lon = store["geometry"]["coordinates"][0]
            store_name = store["properties"].get("name", "Unknown Store")
            store_type = get_store_type(store["properties"].get("categories", []))
            store_address = store["properties"].get("formatted", "No address available")

            # Create popup content
            popup_content = f"""
            <div style='width: 200px'>
                <h4 style='margin: 0 0 5px 0;'>{store_name}</h4>
                <p style='margin: 0 0 5px 0;'><strong>Type:</strong> {store_type}</p>
                <p style='margin: 0;'><strong>Address:</strong> {store_address}</p>
            </div>
            """
            
            folium.Marker(
                [store_lat, store_lon],
                popup=folium.Popup(popup_content, max_width=300),
                icon=folium.Icon(color="green", icon="shopping-cart"),
            ).add_to(m)

    # Save map to file
    map_file = f"maps/map_{uuid.uuid4().hex}.html"
    map_path = os.path.join(app.root_path, "static", map_file)
    m.save(map_path)

    # Ensure the file has the correct permissions
    os.chmod(map_path, 0o644)  # rw-r--r--

    return map_file


# Create database tables before first request
with app.app_context():
    db.create_all()
# def create_tables():
#     db.create_all()


@app.route("/")
def index():
    return render_template(
        "skincare_index.html", current_year=datetime.datetime.now().year
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
        
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        remember = "remember" in request.form
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user, remember=remember)
            flash("Login successful!", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("index"))
        else:
            flash("Invalid email or password. Please try again.", "error")
            
    return render_template("login.html", current_year=datetime.datetime.now().year)


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
        
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        
        # Check if passwords match
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("register"))
            
        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            flash("Username already exists. Please choose another one.", "error")
            return redirect(url_for("register"))
            
        if User.query.filter_by(email=email).first():
            flash(
                "Email already registered. Please login or use another email.", "error"
            )
            return redirect(url_for("register"))
        
        # Create new user
        new_user = User(
            username=username, email=email, first_name=first_name, last_name=last_name
        )
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash("Account created successfully! You can now login.", "success")
        return redirect(url_for("login"))
    
    return render_template("register.html", current_year=datetime.datetime.now().year)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


@app.route("/profile")
@login_required
def profile():
    # Get user's analysis history   
    analysis_history = (
        Analysis.query.filter_by(user_id=current_user.id)
        .order_by(Analysis.created_at.desc())
        .all()
    )
    return render_template(
        "profile.html",
        current_year=datetime.datetime.now().year,
        analysis_history=analysis_history,
    )


@app.route("/view_analysis/<int:analysis_id>")
@login_required
def view_analysis(analysis_id):
    analysis = Analysis.query.get_or_404(analysis_id)
    
    # Ensure user can only view their own analysis
    if analysis.user_id != current_user.id:
        flash("You don't have permission to view this analysis.", "error")
        return redirect(url_for("profile"))
    
    # Convert stored JSON string back to dict
    analysis_data = json.loads(analysis.result_data)
    
    # Initialize results with analysis data and image path
    results = {
        "analysis": analysis_data,
        "image_path": analysis.image_path,
        "map_file": None,
        "nearby_stores": [],
        "using_mock_data": False,
    }
    
    # Get user's location data from request if they want to see nearby stores now
    user_lat = request.args.get("latitude", type=float)
    user_lon = request.args.get("longitude", type=float)
    search_radius = request.args.get("radius", 5000, type=int)
    
    if user_lat and user_lon:
        try:
            # Find nearby stores using current location
            stores = get_nearby_stores(user_lat, user_lon, radius=search_radius)
            
            # Check if we're using mock data
            if stores and len(stores) > 0 and stores[0].get("is_mock", False):
                results["using_mock_data"] = True
                flash(
                    "Using demonstration data for nearby stores since the location API is currently unavailable. These stores are fictional.",
                    "warning",
                )
            
            if stores and len(stores) > 0:
                map_file = create_map(user_lat, user_lon, stores, radius=search_radius)
                
                # Process store data for template
                nearby_stores = []
                for store in stores:
                    props = store["properties"]
                    
                    # Get store name or use a default
                    name = props.get("name", "Cosmetics Store")
                    
                    # Get address components
                    street = props.get("street", "")
                    housenumber = props.get("housenumber", "")
                    address = (
                        f"{housenumber} {street}".strip() if housenumber else street
                    )
                    city = props.get("city", "")
                    full_address = f"{address}, {city}".strip(", ")
                    
                    # Calculate distance in km
                    distance = props.get("distance", 1000) / 1000
                    
                    # Determine what products might be available based on store type
                    store_categories = props.get("categories", "")
                    
                    # Ensure store_categories is a list
                    if isinstance(store_categories, str):
                        if "," in store_categories:
                            store_categories_list = store_categories.split(",")
                        else:
                            store_categories_list = [store_categories]
                    else:
                        store_categories_list = (
                            store_categories if store_categories else []
                        )
                    
                    products_likely = []
                    
                    # Different store types will have different recommended products
                    if any("cosmetics" in cat for cat in store_categories_list):
                        # Cosmetics stores most likely have all recommended products
                        for product in analysis_data.get("products", [])[:2]:
                            if product.get("type"):
                                products_likely.append(product["type"])
                    elif any(
                        "health_and_beauty" in cat for cat in store_categories_list
                    ):
                        # Beauty shops likely have skincare products
                        for product in analysis_data.get("products", []):
                            if product.get("type") and (
                                "Cleanser" in product["type"]
                                or "Moisturizer" in product["type"]
                                or "Cream" in product["type"]
                            ):
                                products_likely.append(product["type"])
                                break
                    elif any(
                        "pharmacy" in cat or "chemist" in cat
                        for cat in store_categories_list
                    ):
                        # Pharmacies might have basic skincare
                        for product in analysis_data.get("products", []):
                            if product.get("type") and (
                                "Cleanser" in product["type"]
                                or "Moisturizer" in product["type"]
                            ):
                                products_likely.append(product["type"])
                                break
                    elif any(
                        "department_store" in cat or "shopping_mall" in cat
                        for cat in store_categories_list
                    ):
                        # Department stores likely have most products but worth calling ahead
                        products_likely.append("Most skincare products")
                    
                    nearby_stores.append(
                        {
                        "name": name,
                        "address": full_address or "Address not available",
                        "distance": f"{distance:.1f} km",
                        "coordinates": {
                            "lat": props.get("lat"),
                            "lng": props.get("lon"),
                        },
                        "products_likely": products_likely,
                            "store_type": get_store_type(store_categories_list),
                        }
                    )
                
                results["map_file"] = map_file.replace("static/", "")
                results["nearby_stores"] = nearby_stores
            else:
                # If no stores found, create a simple map showing just the user's location
                m = folium.Map(location=[user_lat, user_lon], zoom_start=13)
                folium.Marker(
                    [user_lat, user_lon],
                    popup="<b>Your Location</b>",
                    icon=folium.Icon(color="red", icon="home", prefix="fa"),
                ).add_to(m)
                
                # Add a search radius circle
                folium.Circle(
                    radius=search_radius,
                    location=[user_lat, user_lon],
                    color="#4F46E5",
                    fill=True,
                    fill_color="#4F46E5",
                    fill_opacity=0.1,
                    tooltip=f"{search_radius/1000:.0f}km Search Radius - No stores found in this area",
                ).add_to(m)
                
                # Save map to file
                map_file = f"static/maps/map_{uuid.uuid4().hex}.html"
                m.save(os.path.join(app.root_path, map_file))
                
                results["map_file"] = map_file.replace("static/", "")
                results["nearby_stores"] = []
                
                # Flash a message to the user
                flash(
                    f"No cosmetics stores found within {search_radius/1000:.0f}km of your location. Try increasing the search radius or searching in a different location.",
                    "info",
                )
                
        except Exception as e:
            print(f"Error finding nearby stores: {e}")
            flash(
                "An error occurred while searching for nearby stores. Please try again later.",
                "error",
            )
            # Continue without map if there's an error
    
    return render_template(
        "skincare_results.html",
        results=results,
        current_year=datetime.datetime.now().year,
        history_view=True,
    )


@app.route("/analyze", methods=["GET", "POST"])
@login_required
def analyze():
    if request.method == "POST":
        # Check if the post request has the file part
        if "skin_image" not in request.files:
            flash("No file part", "error")
            return redirect(request.url)

        file = request.files["skin_image"]

        # If user does not select file, browser also submits an empty part without filename
        if file.filename == "":
            flash("No selected file", "error")
            return redirect(request.url)

        if file and allowed_file(file.filename):
            # Generate a unique filename to prevent overwriting
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
            file.save(file_path)

            # Get location data if provided
            user_lat = request.form.get("latitude", type=float)
            user_lon = request.form.get("longitude", type=float)
            search_radius = request.form.get("radius", 5000, type=int)

            # Process image with Gemini AI
            try:
                with open(file_path, "rb") as img_file:
                    image_data = img_file.read()
                MODELS = (GEMINI_MODEL, "gemini-2.0-flash", "gemini-1.5-flash")
                ext = file_path.split('.')[-1]
                if ext not in {"png", "jpeg", "webp", "heic", "heif"}:
                    ext = "jpeg"
                data = types.Part.from_bytes(
                    data=image_data,
                    mime_type=f"image/{ext}",
                )
                max_retries = 3
                backoff = 1
                client = genai.Client(api_key=GEMINI_API_KEY)
                for attempt in range(1, max_retries + 1):
                    try:
                        response = client.models.generate_content(
                            model=MODELS[attempt - 1],
                            contents=[
                                skin_analysis_prompt,
                                data,
                            ],
                            config={
                                "response_mime_type": "application/json",
                                "response_schema": Skin,
                            },
                        )
                        ai_response: Skin = response.parsed
                        pprint(ai_response.model_dump())
                        analysis_result = ai_response.model_dump()
                        break
                    except ServerError as e:
                        print(f"Attempt {attempt} failed: {e}")
                        if attempt < max_retries:
                            print(
                                f"ServerError on attempt {attempt}, Retrying in {backoff} seconds..."
                            )
                            time.sleep(backoff)
                            backoff *= 2
                        else:
                            print("All attempts failed. Exiting.")
                            raise
                    except APIError as e:
                        print(f"APIError: {e.message}")
                        raise
                
                # Store analysis in database if user is logged in
                if current_user.is_authenticated:
                    new_analysis = Analysis(
                        user_id=current_user.id,
                        image_path=os.path.join("uploads", unique_filename),
                        result_data=json.dumps(analysis_result),
                    )
                    db.session.add(new_analysis)
                    db.session.commit()
                
                # Initialize variables
                map_file = None
                nearby_stores = []
                using_mock_data = False

                if user_lat and user_lon:
                    try:
                        stores = get_nearby_stores(
                            user_lat, user_lon, radius=search_radius
                        )
                        
                        # Check if we're using mock data
                        if (
                            stores
                            and len(stores) > 0
                            and stores[0].get("is_mock", False)
                        ):
                            using_mock_data = True
                            flash(
                                "Using demonstration data for nearby stores since the location API is currently unavailable. These stores are fictional.",
                                "warning",
                            )
                        
                        if stores and len(stores) > 0:
                            map_file = create_map(
                                user_lat, user_lon, stores, radius=search_radius
                            )

                            # Process store data for template
                            for store in stores:
                                props = store["properties"]
                                
                                # Get store name or use a default
                                name = props.get("name", "Cosmetics Store")
                                
                                # Get address components
                                street = props.get("street", "")
                                housenumber = props.get("housenumber", "")
                                address = (
                                    f"{housenumber} {street}".strip()
                                    if housenumber
                                    else street
                                )
                                city = props.get("city", "")
                                full_address = f"{address}, {city}".strip(", ")
                                
                                # Calculate distance in km
                                distance = props.get("distance", 1000) / 1000
                                
                                # Determine what products might be available based on store type
                                store_categories = props.get("categories", "")
                                
                                # Ensure store_categories is a list
                                if isinstance(store_categories, str):
                                    if "," in store_categories:
                                        store_categories_list = store_categories.split(
                                            ","
                                        )
                                    else:
                                        store_categories_list = [store_categories]
                                else:
                                    store_categories_list = (
                                        store_categories if store_categories else []
                                    )
                                
                                products_likely = []
                                
                                # Different store types will have different recommended products
                                if any(
                                    "cosmetics" in cat for cat in store_categories_list
                                ):
                                    # Cosmetics stores most likely have all recommended products
                                    for product in analysis_result.get("products", [])[
                                        :2
                                    ]:
                                        if product.get("type"):
                                            products_likely.append(product["type"])
                                elif any(
                                    "health_and_beauty" in cat
                                    for cat in store_categories_list
                                ):
                                    # Beauty shops likely have skincare products
                                    for product in analysis_result.get("products", []):
                                        if product.get("type") and (
                                            "Cleanser" in product["type"]
                                            or "Moisturizer" in product["type"]
                                            or "Cream" in product["type"]
                                        ):
                                            products_likely.append(product["type"])
                                            break
                                elif any(
                                    "pharmacy" in cat or "chemist" in cat
                                    for cat in store_categories_list
                                ):
                                    # Pharmacies might have basic skincare
                                    for product in analysis_result.get("products", []):
                                        if product.get("type") and (
                                            "Cleanser" in product["type"]
                                            or "Moisturizer" in product["type"]
                                        ):
                                            products_likely.append(product["type"])
                                            break
                                elif any(
                                    "department_store" in cat or "shopping_mall" in cat
                                    for cat in store_categories_list
                                ):
                                    # Department stores likely have most products but worth calling ahead
                                    products_likely.append("Most skincare products")
                                
                                nearby_stores.append(
                                    {
                                    "name": name,
                                        "address": full_address
                                        or "Address not available",
                                    "distance": f"{distance:.1f} km",
                                    "coordinates": {
                                        "lat": props.get("lat"),
                                        "lng": props.get("lon"),
                                    },
                                    "products_likely": products_likely,
                                        "store_type": get_store_type(
                                            store_categories_list
                                        ),
                                    }
                                )
                        else:
                            # If no stores found, create a simple map showing just the user's location
                            m = folium.Map(location=[user_lat, user_lon], zoom_start=13)
                            folium.Marker(
                                [user_lat, user_lon],
                                popup="<b>Your Location</b>",
                                icon=folium.Icon(color="red", icon="home", prefix="fa"),
                            ).add_to(m)
                            
                            # Add a search radius circle
                            folium.Circle(
                                radius=search_radius,
                                location=[user_lat, user_lon],
                                color="#4F46E5",
                                fill=True,
                                fill_color="#4F46E5",
                                fill_opacity=0.1,
                                tooltip=f"{search_radius/1000:.0f}km Search Radius - No stores found in this area",
                            ).add_to(m)
                            
                            # Save map to file
                            map_file = f"static/maps/map_{uuid.uuid4().hex}.html"
                            m.save(os.path.join(app.root_path, map_file))
                            
                            # Flash a message to the user
                            flash(
                                f"No cosmetics stores found within {search_radius/1000:.0f}km of your location. Try increasing the search radius or searching in a different location.",
                                "info",
                            )
                    
                    except Exception as e:
                        print(f"Error creating map: {e}")
                        flash(
                            "An error occurred while searching for nearby stores. Please try again later.",
                            "error",
                        )
                        # If map creation fails, continue without the map
                
                # Store results in session
                session["analysis_result"] = analysis_result
                session["image_path"] = os.path.join("uploads", unique_filename)
                session["map_file"] = map_file
                session["nearby_stores"] = nearby_stores
                session["using_mock_data"] = using_mock_data
                # Store location data in session for later use
                if user_lat and user_lon:
                    session["user_lat"] = user_lat
                    session["user_lon"] = user_lon
                    session["search_radius"] = search_radius

                return redirect(url_for("results"))

            except Exception as e:
                print(f"Error analyzing image: {e}")
                flash(f"Error analyzing image: {str(e)}", "error")
                return redirect(request.url)
        else:
            flash("File type not allowed", "error")
            return redirect(request.url)

    return render_template(
        "skincare_analyze.html", current_year=datetime.datetime.now().year
    )


@app.route("/results")
def results():
    # Check if we have results in the session
    if "analysis_result" not in session or "image_path" not in session:
        flash("No analysis results found. Please upload an image first.", "error")
        return redirect(url_for("analyze"))

    # Get location data from session
    user_lat = session.get("user_lat")
    user_lon = session.get("user_lon")
    search_radius = session.get("search_radius", 5000)

    # Initialize results dictionary
    results = {
        "analysis": session["analysis_result"],
        "image_path": session["image_path"],
        "map_file": session.get("map_file"),
        "nearby_stores": session.get("nearby_stores", []),
        "using_mock_data": session.get("using_mock_data", False),
        "user_lat": user_lat,
        "user_lon": user_lon,
        "search_radius": search_radius,
    }

    # If we have location data but no nearby stores, try to get them
    if user_lat and user_lon and not session.get("nearby_stores"):
        try:
            stores = get_nearby_stores(user_lat, user_lon, radius=search_radius)

            # Check if we're using mock data
            if stores and len(stores) > 0 and stores[0].get("is_mock", False):
                results["using_mock_data"] = True
                flash(
                    "Using demonstration data for nearby stores since the location API is currently unavailable. These stores are fictional.",
                    "warning",
                )

            if stores and len(stores) > 0:
                map_file = create_map(user_lat, user_lon, stores, radius=search_radius)
                session["map_file"] = map_file
                session["nearby_stores"] = stores
                results["map_file"] = map_file
                results["nearby_stores"] = stores
            else:
                # If no stores found, create a simple map showing just the user's location
                m = folium.Map(location=[user_lat, user_lon], zoom_start=13)
                folium.Marker(
                    [user_lat, user_lon],
                    popup="<b>Your Location</b>",
                    icon=folium.Icon(color="red", icon="home", prefix="fa"),
                ).add_to(m)

                # Add a search radius circle
                folium.Circle(
                    radius=search_radius,
                    location=[user_lat, user_lon],
                    color="#4F46E5",
                    fill=True,
                    fill_color="#4F46E5",
                    fill_opacity=0.1,
                    tooltip=f"{search_radius/1000:.0f}km Search Radius - No stores found in this area",
                ).add_to(m)

                # Save map to file
                map_file = f"static/maps/map_{uuid.uuid4().hex}.html"
                m.save(os.path.join(app.root_path, map_file))

                session["map_file"] = map_file
                results["map_file"] = map_file
                results["nearby_stores"] = []

                # Flash a message to the user
                flash(
                    f"No cosmetics stores found within {search_radius/1000:.0f}km of your location. Try increasing the search radius or searching in a different location.",
                    "info",
                )

        except Exception as e:
            print(f"Error getting nearby stores: {e}")
            flash(
                "An error occurred while searching for nearby stores. Please try again later.",
                "error",
            )

    return render_template(
        "skincare_results.html",
        results=results,
        current_year=datetime.datetime.now().year,
    )


@app.route("/about")
def about():
    return render_template(
        "skincare_about.html", current_year=datetime.datetime.now().year
    )


@app.route("/delete_analysis/<int:analysis_id>", methods=["POST"])
@login_required
def delete_analysis(analysis_id):
    analysis = Analysis.query.get_or_404(analysis_id)

    # Check if the analysis belongs to the current user
    if analysis.user_id != current_user.id:
        flash("You do not have permission to delete this analysis.", "error")
        return redirect(url_for("profile"))

    try:
        # Delete associated files
        if analysis.image_path:
            try:
                os.remove(
                    os.path.join(app.config["UPLOAD_FOLDER"], analysis.image_path)
                )
            except OSError:
                pass  # Ignore if file doesn't exist

        # Delete the analysis from database
        db.session.delete(analysis)
        db.session.commit()

        flash("Analysis deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash("Error deleting analysis. Please try again.", "error")
        print(f"Error deleting analysis: {str(e)}")

    return redirect(url_for("profile"))


if __name__ == "__main__":
    app.run(debug=True, port=5050)
