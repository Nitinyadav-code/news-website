from datetime import datetime
from flask_login import UserMixin
from app import db, login_manager

# Association table for many-to-many relationship between posts and tags
post_tags = db.Table('post_tags',
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    posts = db.relationship('Post', backref='author', lazy=True)

    def __repr__(self):
        return f"User('{self.username}', '{self.email}')"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    posts = db.relationship('Post', backref='category', lazy=True)

    def __repr__(self):
        return f"Category('{self.name}', '{self.slug}')"

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships defined through the post_tags table

    def __repr__(self):
        return f"Tag('{self.name}', '{self.slug}')"

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    summary = db.Column(db.Text, nullable=True)
    content = db.Column(db.Text, nullable=False)
    published = db.Column(db.Boolean, default=False)
    featured_image = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    meta_description = db.Column(db.String(255), nullable=True)
    meta_keywords = db.Column(db.String(255), nullable=True)
    
    # Foreign keys
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    
    # Relationships
    tags = db.relationship('Tag', secondary=post_tags, lazy='subquery',
                          backref=db.backref('posts', lazy=True))

    def __repr__(self):
        return f"Post('{self.title}', '{self.slug}')"

class Media(db.Model):
    """Model for storing media files information"""
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(255), nullable=False, unique=True)
    filetype = db.Column(db.String(50), nullable=False)  # image/pdf/etc
    filesize = db.Column(db.Integer, nullable=False)  # size in bytes
    alt_text = db.Column(db.String(255))
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    uploader = db.relationship('User', backref='media_uploads')
    
    def __repr__(self):
        return f"Media('{self.filename}', '{self.filetype}')"
