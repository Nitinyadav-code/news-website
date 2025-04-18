import os
from datetime import datetime
from flask import Flask, render_template, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from dotenv import load_dotenv
from sqlalchemy import func
from flask_compress import Compress
from werkzeug.utils import secure_filename
import uuid
import time

# Load environment variables from .env file
load_dotenv()

# Create Flask app with correct template folder path
app = Flask(__name__, 
            template_folder='app/templates',
            static_folder='app/static')

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-dev-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///blog.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Function to save uploaded images
def save_image(file, image_type):
    """
    Save uploaded image to the appropriate directory
    
    Args:
        file: The uploaded file object
        image_type: Type of image ('featured' or 'content')
    
    Returns:
        path: Relative path to the saved image (for storing in database)
    """
    # Generate unique filename using hex representation of uuid4 and timestamp
    unique_filename = uuid.uuid4().hex[:16] + str(int(time.time()))[-6:]
    
    # Get file extension
    _, file_extension = os.path.splitext(file.filename)
    
    # Create safe filename
    filename = unique_filename + file_extension.lower()
    
    # Determine directory path based on image type
    if image_type == 'featured':
        directory = os.path.join('media', 'featured')
    else:  # content
        directory = os.path.join('media', 'content')
    
    # Ensure directory exists
    full_directory = os.path.join(app.static_folder, directory)
    if not os.path.exists(full_directory):
        os.makedirs(full_directory)
    
    # Save the file
    file_path = os.path.join(full_directory, filename)
    file.save(file_path)
    
    # Return relative path for database storage
    return os.path.join(directory, filename)

# Add compression for faster page loads
compress = Compress()
compress.init_app(app)

# Add cache control headers for static assets
@app.after_request
def add_cache_control(response):
    if request.path.startswith('/static'):
        # Cache static files for 1 year (31536000 seconds)
        if 'css' in request.path or 'js' in request.path:
            response.cache_control.max_age = 31536000
        # Cache images for 1 week (604800 seconds)
        elif 'img' in request.path or 'uploads' in request.path:
            response.cache_control.max_age = 604800
    return response

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# Import routes after initializing db to avoid circular imports
from routes import *
from models import User, Post, Category, Tag

# Global template variables
@app.context_processor
def inject_globals():
    # Get all categories for the sidebar
    categories = Category.query.all()
    
    # Get popular tags (those associated with most posts)
    popular_tags = Tag.query.join(Tag.posts).group_by(Tag.id).order_by(func.count().desc()).limit(10).all()
    
    # Get recent posts for footer or sidebar
    recent_posts = Post.query.filter_by(published=True).order_by(Post.created_at.desc()).limit(5).all()
    
    # Get the current year for copyright
    current_year = datetime.now().year
    
    # Return a dictionary of global variables
    return {
        'categories': categories,
        'popular_tags': popular_tags,
        'recent_posts': recent_posts,
        'current_year': current_year
    }

# Initialize database with admin user on first run
@app.before_first_request
def create_tables_and_admin():
    db.create_all()
    
    # Check if there are any users
    if not User.query.first():
        from werkzeug.security import generate_password_hash
        
        # Create admin user
        admin = User(
            username='admin',
            email='admin@example.com',
            password_hash=generate_password_hash('admin123'),
            is_admin=True
        )
        db.session.add(admin)
        
        # Create some initial categories
        categories = [
            Category(name='Technology', slug='technology'),
            Category(name='Travel', slug='travel'),
            Category(name='Food', slug='food'),
            Category(name='Lifestyle', slug='lifestyle')
        ]
        for category in categories:
            db.session.add(category)
        
        # Create some initial tags
        tags = [
            Tag(name='Python', slug='python'),
            Tag(name='Flask', slug='flask'),
            Tag(name='Web Development', slug='web-development'),
            Tag(name='Tips', slug='tips')
        ]
        for tag in tags:
            db.session.add(tag)
        
        db.session.commit()
        
        print('Admin user created! Username: admin, Password: admin123')
        print('IMPORTANT: Change the admin password after first login!')

if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG', 'True').lower() == 'true')
