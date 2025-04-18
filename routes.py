import os
import secrets
from datetime import datetime, timedelta
from PIL import Image
from slugify import slugify
import bleach
from flask import render_template, url_for, flash, redirect, request, abort, jsonify
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from app import app, db
from models import User, Post, Category, Tag, Media
from forms import MediaForm, MediaUploadForm

# Helper functions
def save_image(form_picture, image_type='content'):
    """Save uploaded images with a secure filename to the unified media folder structure
    
    Args:
        form_picture: The uploaded file object
        image_type: Either 'featured' or 'content' to determine subdirectory
    """
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    
    # Define the subdirectory based on image type
    if image_type not in ['featured', 'content']:
        # Default to content if invalid type provided
        image_type = 'content'
    
    # Set the folder path relative to static folder
    folder = f"media/{image_type}"
    
    # Use app.static_folder to get the correct absolute path
    upload_folder = os.path.join(app.static_folder, folder)
    
    # Create folder if it doesn't exist
    os.makedirs(upload_folder, exist_ok=True)
    
    # Save the image
    picture_path = os.path.join(upload_folder, picture_fn)
    
    # Resize image to save space
    output_size = (1200, 800)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)
    
    # Return the relative path to be stored in the database
    # Always use forward slashes for web URLs, not os.path.join which uses backslashes on Windows
    return f"{folder}/{picture_fn}"

def clean_html(html_content):
    """Clean HTML content to prevent XSS vulnerabilities"""
    allowed_tags = [
        'a', 'abbr', 'acronym', 'b', 'blockquote', 'br', 'code', 'div', 'em',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img', 'li', 'ol', 'p',
        'pre', 'span', 'strong', 'table', 'tbody', 'td', 'th', 'thead', 'tr', 'ul'
    ]
    allowed_attrs = {
        '*': ['class', 'style'],
        'a': ['href', 'rel', 'target'],
        'img': ['src', 'alt', 'width', 'height']
    }
    cleaned = bleach.clean(
        html_content,
        tags=allowed_tags,
        attributes=allowed_attrs,
        strip=True
    )
    return cleaned

def admin_required(f):
    """Decorator for routes that require admin privileges"""
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Error Handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html', title='Page Not Found'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('errors/500.html', title='Server Error'), 500

@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html', title='Forbidden'), 403

# Public Routes
@app.route('/')
@app.route('/index')
def index():
    page = request.args.get('page', 1, type=int)
    posts = Post.query.filter_by(published=True).order_by(Post.created_at.desc()).paginate(page=page, per_page=6)
    return render_template('index.html', title='Home', posts=posts)

@app.route('/post/<string:slug>')
def post(slug):
    post = Post.query.filter_by(slug=slug).first_or_404()
    
    # Only show published posts to non-admin users
    if not post.published and (not current_user.is_authenticated or not current_user.is_admin):
        abort(404)
    
    # Get related posts based on tags or category
    related_posts = []
    if post.tags:
        tag_ids = [tag.id for tag in post.tags]
        related_posts = Post.query.filter(
            Post.id != post.id,
            Post.published == True,
            Post.tags.any(Tag.id.in_(tag_ids))
        ).order_by(Post.created_at.desc()).limit(2).all()
    
    # If not enough related posts by tag, add some from same category
    if len(related_posts) < 2 and post.category:
        category_related = Post.query.filter(
            Post.id != post.id,
            Post.published == True,
            Post.category_id == post.category_id
        ).order_by(Post.created_at.desc()).limit(2 - len(related_posts)).all()
        
        related_posts.extend(category_related)
    
    return render_template('post.html', title=post.title, post=post, related_posts=related_posts)

@app.route('/category/<string:slug>')
def category(slug):
    category = Category.query.filter_by(slug=slug).first_or_404()
    page = request.args.get('page', 1, type=int)
    posts = Post.query.filter_by(category_id=category.id, published=True).order_by(
        Post.created_at.desc()).paginate(page=page, per_page=6)
    
    return render_template('category.html', title=f'Category: {category.name}', 
                          category=category, posts=posts)

@app.route('/tag/<string:slug>')
def tag(slug):
    tag = Tag.query.filter_by(slug=slug).first_or_404()
    page = request.args.get('page', 1, type=int)
    posts = Post.query.filter(Post.tags.contains(tag), Post.published == True).order_by(
        Post.created_at.desc()).paginate(page=page, per_page=6)
    
    return render_template('tag.html', title=f'Tag: {tag.name}', 
                          tag=tag, posts=posts)

@app.route('/search')
def search():
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    
    if not query:
        return redirect(url_for('index'))
    
    # Search posts by title, content, summary
    posts = Post.query.filter(
        Post.published == True,
        (Post.title.contains(query) | 
         Post.content.contains(query) | 
         Post.summary.contains(query))
    ).order_by(Post.created_at.desc()).paginate(page=page, per_page=10)
    
    # Get categories with post counts
    categories = Category.query.all()
    categories_with_counts = []
    for category in categories:
        post_count = Post.query.filter_by(category_id=category.id, published=True).count()
        category.post_count = post_count
        categories_with_counts.append(category)
    
    # Get popular tags
    popular_tags = Tag.query.join(Tag.posts).group_by(Tag.id).order_by(db.func.count().desc()).limit(10).all()
    
    return render_template('search.html', title=f'Search Results for: {query}',
                          query=query, posts=posts, categories=categories_with_counts,
                          popular_tags=popular_tags)

@app.route('/about')
def about():
    return render_template('about.html', title='About Us')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    # In a real application, you would send an email or store the contact submission
    if request.method == 'POST':
        flash('Your message has been sent successfully!', 'success')
        return redirect(url_for('contact'))
    
    return render_template('contact.html', title='Contact Us')

# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            else:
                if user.is_admin:
                    return redirect(url_for('admin'))
                return redirect(url_for('index'))
        else:
            flash('Login failed. Please check your email and password.', 'danger')
    
    return render_template('login.html', title='Login')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# Admin Routes
@app.route('/admin')
@admin_required
def admin():
    recent_posts = Post.query.order_by(Post.created_at.desc()).limit(5).all()
    
    # Add stats for dashboard counters
    stats = {
        'posts_count': Post.query.count(),
        'categories_count': Category.query.count(),
        'tags_count': Tag.query.count(),
        'users_count': User.query.count()
    }
    
    # Add system information for the system info panel
    import platform
    import flask
    system_info = {
        'python_version': platform.python_version(),
        'flask_version': flask.__version__,
        'database': 'SQLite',
        'environment': 'Development' if app.debug else 'Production'
    }
    
    return render_template('admin/dashboard.html', title='Admin Dashboard', 
                          recent_posts=recent_posts, stats=stats, system_info=system_info)

@app.route('/admin/posts')
@admin_required
def admin_posts():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('q', '')
    
    if search_query:
        posts = Post.query.filter(
            Post.title.contains(search_query) | 
            Post.content.contains(search_query)
        ).order_by(Post.created_at.desc()).paginate(page=page, per_page=10)
    else:
        posts = Post.query.order_by(Post.created_at.desc()).paginate(page=page, per_page=10)
    
    return render_template('admin/posts.html', title='Manage Posts', posts=posts)

@app.route('/admin/new-post', methods=['GET', 'POST'])
@admin_required
def new_post():
    categories = Category.query.all()
    tags = Tag.query.all()
    
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        summary = request.form.get('summary')
        category_id = request.form.get('category_id') or None
        tag_ids = request.form.getlist('tags')
        meta_description = request.form.get('meta_description')
        meta_keywords = request.form.get('meta_keywords')
        published = 'published' in request.form
        
        # Clean HTML content
        clean_content = clean_html(content)
        
        # Create slug from title
        slug = slugify(title)
        
        # Check for slug uniqueness and modify if needed
        base_slug = slug
        count = 1
        while Post.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{count}"
            count += 1
        
        # Handle featured image upload
        featured_image = None
        if 'featured_image' in request.files and request.files['featured_image'].filename:
            try:
                featured_image = save_image(request.files['featured_image'], image_type='featured')
            except Exception as e:
                flash(f'Error uploading image: {str(e)}', 'danger')
                return render_template('admin/post_form.html', title='New Post', 
                                     categories=categories, tags=tags)
        
        # Create new post
        post = Post(
            title=title,
            slug=slug,
            content=clean_content,
            summary=summary,
            category_id=category_id,
            featured_image=featured_image,
            meta_description=meta_description,
            meta_keywords=meta_keywords,
            published=published,
            author_id=current_user.id
        )
        
        # Add selected tags
        if tag_ids:
            post.tags = [Tag.query.get(tag_id) for tag_id in tag_ids]
        
        db.session.add(post)
        db.session.commit()
        
        flash('Post created successfully!', 'success')
        return redirect(url_for('admin_posts'))
    
    return render_template('admin/post_form.html', title='New Post', 
                         categories=categories, tags=tags)

@app.route('/admin/edit-post/<int:post_id>', methods=['GET', 'POST'])
@admin_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    categories = Category.query.all()
    tags = Tag.query.all()
    
    if request.method == 'POST':
        post.title = request.form.get('title')
        post.content = clean_html(request.form.get('content'))
        post.summary = request.form.get('summary')
        post.category_id = request.form.get('category_id') or None
        post.meta_description = request.form.get('meta_description')
        post.meta_keywords = request.form.get('meta_keywords')
        post.published = 'published' in request.form
        post.updated_at = datetime.utcnow()
        
        # Handle featured image upload
        if 'featured_image' in request.files and request.files['featured_image'].filename:
            try:
                post.featured_image = save_image(request.files['featured_image'], image_type='featured')
            except Exception as e:
                flash(f'Error uploading image: {str(e)}', 'danger')
                return render_template('admin/post_form.html', title='Edit Post', 
                                    post=post, categories=categories, tags=tags)
        
        # Update tags
        tag_ids = request.form.getlist('tags')
        post.tags = [Tag.query.get(tag_id) for tag_id in tag_ids]
        
        db.session.commit()
        
        flash('Post updated successfully!', 'success')
        return redirect(url_for('admin_posts'))
    
    return render_template('admin/post_form.html', title='Edit Post', 
                         post=post, categories=categories, tags=tags)

@app.route('/admin/delete-post/<int:post_id>', methods=['POST'])
@admin_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    # Delete featured image file if it exists
    if post.featured_image:
        try:
            # Use app.static_folder to get the correct path
            image_path = os.path.join(app.static_folder, post.featured_image)
            if os.path.exists(image_path):
                os.remove(image_path)
        except Exception as e:
            app.logger.error(f"Error deleting image file: {str(e)}")
    
    db.session.delete(post)
    db.session.commit()
    
    flash('Post deleted successfully!', 'success')
    return redirect(url_for('admin_posts'))

# Category routes
@app.route('/admin/categories')
@admin_required
def admin_categories():
    categories = Category.query.all()
    return render_template('admin/categories.html', title='Manage Categories', categories=categories)

@app.route('/admin/new-category', methods=['GET', 'POST'])
@admin_required
def new_category():
    if request.method == 'POST':
        name = request.form.get('name')
        
        # Create slug from name
        slug = slugify(name)
        
        # Check for slug uniqueness and modify if needed
        base_slug = slug
        count = 1
        while Category.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{count}"
            count += 1
        
        category = Category(name=name, slug=slug)
        db.session.add(category)
        db.session.commit()
        
        flash('Category created successfully!', 'success')
        return redirect(url_for('admin_categories'))
    
    return render_template('admin/category_form.html', title='New Category')

@app.route('/admin/edit-category/<int:category_id>', methods=['GET', 'POST'])
@admin_required
def edit_category(category_id):
    category = Category.query.get_or_404(category_id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        
        # Update slug if name changed
        if name != category.name:
            slug = slugify(name)
            
            # Check for slug uniqueness and modify if needed
            base_slug = slug
            count = 1
            while Category.query.filter(Category.id != category_id, Category.slug == slug).first():
                slug = f"{base_slug}-{count}"
                count += 1
                
            category.slug = slug
        
        category.name = name
        db.session.commit()
        
        flash('Category updated successfully!', 'success')
        return redirect(url_for('admin_categories'))
    
    return render_template('admin/category_form.html', title='Edit Category', category=category)

@app.route('/admin/delete-category/<int:category_id>', methods=['POST'])
@admin_required
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    
    # Don't delete category if it has posts
    if category.posts.count() > 0:
        flash('Cannot delete category that has posts!', 'danger')
        return redirect(url_for('admin_categories'))
    
    db.session.delete(category)
    db.session.commit()
    
    flash('Category deleted successfully!', 'success')
    return redirect(url_for('admin_categories'))

# Tag routes
@app.route('/admin/tags')
@admin_required
def admin_tags():
    tags = Tag.query.all()
    return render_template('admin/tags.html', title='Manage Tags', tags=tags)

@app.route('/admin/new-tag', methods=['GET', 'POST'])
@admin_required
def new_tag():
    if request.method == 'POST':
        name = request.form.get('name')
        
        # Create slug from name
        slug = slugify(name)
        
        # Check for slug uniqueness and modify if needed
        base_slug = slug
        count = 1
        while Tag.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{count}"
            count += 1
        
        tag = Tag(name=name, slug=slug)
        db.session.add(tag)
        db.session.commit()
        
        flash('Tag created successfully!', 'success')
        return redirect(url_for('admin_tags'))
    
    return render_template('admin/tag_form.html', title='New Tag')

@app.route('/admin/edit-tag/<int:tag_id>', methods=['GET', 'POST'])
@admin_required
def edit_tag(tag_id):
    tag = Tag.query.get_or_404(tag_id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        
        # Update slug if name changed
        if name != tag.name:
            slug = slugify(name)
            
            # Check for slug uniqueness and modify if needed
            base_slug = slug
            count = 1
            while Tag.query.filter(Tag.id != tag_id, Tag.slug == slug).first():
                slug = f"{base_slug}-{count}"
                count += 1
                
            tag.slug = slug
        
        tag.name = name
        db.session.commit()
        
        flash('Tag updated successfully!', 'success')
        return redirect(url_for('admin_tags'))
    
    return render_template('admin/tag_form.html', title='Edit Tag', tag=tag)

@app.route('/admin/delete-tag/<int:tag_id>', methods=['POST'])
@admin_required
def delete_tag(tag_id):
    tag = Tag.query.get_or_404(tag_id)
    
    # Remove the tag from posts but don't delete the posts
    db.session.delete(tag)
    db.session.commit()
    
    flash('Tag deleted successfully!', 'success')
    return redirect(url_for('admin_tags'))

# User routes
@app.route('/admin/users')
@admin_required
def admin_users():
    users = User.query.all()
    return render_template('admin/users.html', title='Manage Users', users=users)

@app.route('/admin/new-user', methods=['GET', 'POST'])
@admin_required
def new_user():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        is_admin = 'is_admin' in request.form
        
        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'danger')
            return render_template('admin/user_form.html', title='New User')
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists!', 'danger')
            return render_template('admin/user_form.html', title='New User')
        
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            is_admin=is_admin
        )
        
        db.session.add(user)
        db.session.commit()
        
        flash('User created successfully!', 'success')
        return redirect(url_for('admin_users'))
    
    return render_template('admin/user_form.html', title='New User')

@app.route('/admin/edit-user/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        is_admin = 'is_admin' in request.form
        
        # Check if username already exists for a different user
        if User.query.filter(User.id != user_id, User.username == username).first():
            flash('Username already exists!', 'danger')
            return render_template('admin/user_form.html', title='Edit User', user=user)
        
        # Check if email already exists for a different user
        if User.query.filter(User.id != user_id, User.email == email).first():
            flash('Email already exists!', 'danger')
            return render_template('admin/user_form.html', title='Edit User', user=user)
        
        user.username = username
        user.email = email
        if password:
            user.password_hash = generate_password_hash(password)
        user.is_admin = is_admin
        
        db.session.commit()
        
        flash('User updated successfully!', 'success')
        return redirect(url_for('admin_users'))
    
    return render_template('admin/user_form.html', title='Edit User', user=user)

@app.route('/admin/delete-user/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # Prevent deleting your own account
    if user.id == current_user.id:
        flash('You cannot delete your own account!', 'danger')
        return redirect(url_for('admin_users'))
    
    # Reassign posts to current user
    for post in user.posts:
        post.author_id = current_user.id
    
    db.session.delete(user)
    db.session.commit()
    
    flash('User deleted successfully!', 'success')
    return redirect(url_for('admin_users'))

# SEO Improvements - Sitemap
@app.route('/sitemap.xml')
def sitemap():
    """Generate sitemap.xml for better search engine indexing"""
    pages = []
    ten_days_ago = datetime.utcnow() - timedelta(days=10)
    
    # Add static pages
    for rule in app.url_map.iter_rules():
        # Only include GET routes that don't require parameters and aren't admin routes
        if ('GET' in rule.methods and 
            len(rule.arguments) == 0 and 
            not rule.rule.startswith('/admin') and
            not rule.rule.startswith('/static') and
            not rule.rule.startswith('/login') and
            'sitemap' not in rule.endpoint):
            
            pages.append({
                'loc': url_for(rule.endpoint, _external=True),
                'lastmod': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S'),
                'changefreq': 'weekly',
                'priority': '0.8'
            })
    
    # Add all published blog posts
    posts = Post.query.filter_by(published=True).all()
    for post in posts:
        # Use the post's updated_at date, or created_at if not updated
        lastmod = post.updated_at or post.created_at
        
        pages.append({
            'loc': url_for('post', slug=post.slug, _external=True),
            'lastmod': lastmod.strftime('%Y-%m-%dT%H:%M:%S'),
            'changefreq': 'monthly',
            'priority': '0.9'
        })
    
    # Add all categories
    categories = Category.query.all()
    for category in categories:
        pages.append({
            'loc': url_for('category', slug=category.slug, _external=True),
            'lastmod': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S'),
            'changefreq': 'weekly',
            'priority': '0.8'
        })
    
    # Add all tags
    tags = Tag.query.all()
    for tag in tags:
        pages.append({
            'loc': url_for('tag', slug=tag.slug, _external=True),
            'lastmod': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S'),
            'changefreq': 'weekly',
            'priority': '0.7'
        })
    
    sitemap_xml = render_template('sitemap.xml', pages=pages)
    response = app.response_class(sitemap_xml, mimetype='application/xml')
    return response

# Generate robots.txt
@app.route('/robots.txt')
def robots_txt():
    robots_content = f"""
User-agent: *
Allow: /
Sitemap: {request.host_url}sitemap.xml
Disallow: /admin/
Disallow: /login/
Disallow: /register/
    """
    return app.response_class(robots_content, mimetype='text/plain')

# Editor Image Upload Route
@app.route('/admin/upload-editor-image', methods=['POST'])
@admin_required
def upload_editor_image():
    """Handle AJAX image uploads from the TinyMCE editor"""
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    
    image_file = request.files['image']
    
    if image_file.filename == '':
        return jsonify({'error': 'No image selected'}), 400
    
    try:
        # Save the image to the content subfolder
        image_path = save_image(image_file, image_type='content')
        image_url = url_for('static', filename=image_path, _external=True)
        
        return jsonify({
            'success': True,
            'url': image_url
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Admin media gallery routes
@app.route('/admin/media')
@admin_required
def admin_media():
    """Admin media gallery page"""
    # Get all media files from database
    media_files = Media.query.order_by(Media.created_at.desc()).all()
    
    # Prepare the media upload form
    form = MediaForm()
    
    # Process media files to match expected template format
    images = []
    for media in media_files:
        # Extract the image type from the filepath (featured or content)
        image_type = 'content'  # default
        if 'featured' in media.filepath:
            image_type = 'featured'
            
        images.append({
            'id': media.id,
            'filename': media.filename,
            'path': media.filepath,
            'type': image_type,
            'date_uploaded': media.created_at
        })
    
    return render_template('admin/media.html', title='Media Gallery', images=images, form=form)

@app.route('/admin/media/upload', methods=['POST'])
@admin_required
def admin_upload_image():
    """Handle image upload for media gallery"""
    form = MediaForm()
    
    if form.validate_on_submit():
        try:
            # Save the image file
            image_path = save_image(form.image.data, image_type=form.image_type.data)
            
            # Get file size in bytes
            file_path = os.path.join(app.static_folder, image_path)
            file_size = os.path.getsize(file_path)
            
            # Get file extension to determine type
            _, file_ext = os.path.splitext(form.image.data.filename)
            file_type = f"image/{file_ext.replace('.', '')}"
            
            # Create new media record
            new_media = Media(
                filename=secure_filename(form.image.data.filename),
                filepath=image_path,
                filetype=file_type,
                filesize=file_size,
                alt_text=form.alt_text.data if form.alt_text.data else '',
                uploaded_by=current_user.id
            )
            
            db.session.add(new_media)
            db.session.commit()
            
            flash('Image uploaded successfully!', 'success')
        except Exception as e:
            flash(f'Error uploading image: {str(e)}', 'danger')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{getattr(form, field).label.text}: {error}', 'danger')
    
    return redirect(url_for('admin_media'))

@app.route('/admin/media/delete/<int:image_id>', methods=['POST'])
@admin_required
def admin_delete_image(image_id):
    """Delete an image from the media gallery"""
    media = Media.query.get_or_404(image_id)
    
    try:
        # First delete the file from the filesystem
        file_path = os.path.join(app.static_folder, media.filepath)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Then delete the database record
        db.session.delete(media)
        db.session.commit()
        flash('Image deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting image: {str(e)}', 'danger')
    
    return redirect(url_for('admin_media'))