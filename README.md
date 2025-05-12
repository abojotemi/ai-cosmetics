# AI Cosmetics - AI Skincare Recommender

AI Cosmetics is an AI-powered web application that analyzes user-uploaded skin photos and provides personalized skincare product recommendations along with nearby store locations.

## Features

- **AI Skin Analysis:** Upload a photo of your skin for instant analysis
- **Personalized Recommendations:** Get product suggestions tailored to your skin type and concerns
- **Store Locator:** Find nearby stores with your recommended products
- **Modern UI:** Clean, responsive design with Tailwind CSS
- **Dynamic Templates:** Manage content through an admin interface
- **UI Components:** Ready-to-use elements with Flowbite
- **SEO-friendly Structure:** Optimized for search engines

## Tech Stack

- Flask
- Tailwind CSS
- OpenCV for image processing
- Leaflet.js for interactive maps

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/AI Cosmetics.git
   cd AI Cosmetics
   ```

2. Set up a virtual environment:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows, use: .venv\Scripts\activate
   ```

3. Install Python dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Install Node.js dependencies:
   ```
   npm install
   ```

5. Build Tailwind CSS:
   ```
   npm run build
   ```

## Running the Application

1. Start the Flask development server:
   ```
   python app.py
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:5050
   ```

## Development

For active development with Tailwind CSS watching for changes:
```
npm run dev
```

## Project Structure

- `/static` - Static assets (CSS, JS, images)
- `/templates` - Jinja2 HTML templates
- `/static/uploads` - User-uploaded images (created on first run)
- `app.py` - Main Flask application

## AI Analysis

The app uses computer vision techniques to analyze skin images:
- Color analysis for skin tone and undertones
- Texture analysis for skin concerns
- Feature detection for specific issues

In a production environment, this would be connected to a more sophisticated machine learning model.

## License

[MIT License](LICENSE.md)

## Screenshots

![Home Page](static/img/screenshot-home.jpg)
![Analysis Page](static/img/screenshot-analyze.jpg)
![Results Page](static/img/screenshot-results.jpg)

## Content Management

You can manage the website content through the admin interface:

1. Navigate to `/admin` in your browser
2. Log in with the default password `admin` (you can change this in the `app.py` file)
3. Edit the content as needed and save changes

All content is stored in `static/content/site_content.json` and loaded dynamically.

## Components

The starter includes several pre-built UI components:

- Navigation bar with mobile responsiveness
- Hero section with customizable content
- Feature grid layout
- Call-to-action sections
- Forms with validation
- UI toolkit with modals, carousels, tabs, etc.

## Customization

### Colors

The color scheme uses:
- YinMn Blue (#26547c) - Primary color
- Crayola (#ef476f) - Secondary color
- Sunglow (#ffd166) - Accent color
- Emerald (#06d6a0) - Success color
- Baby Powder (#fffcf9) - Light background

These colors are defined as CSS variables in `templates/_base.html` and can be modified to suit your design needs.

## Deployment

To deploy to production:

1. Set appropriate environment variables:
   ```
   export FLASK_ENV=production
   export SECRET_KEY=your-secure-secret-key
   export ADMIN_PASSWORD=your-secure-admin-password
   ```

2. Build the production CSS:
   ```
   npm run build
   ```

3. Use a production WSGI server like Gunicorn:
   ```
   gunicorn app:app
   ```
