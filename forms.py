from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, TextAreaField, BooleanField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, Email, URL, Optional

class MediaUploadForm(FlaskForm):
    """Form for uploading media files"""
    file = FileField('Media File', validators=[
        FileRequired(),
        FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'], 'Images only!')
    ])
    alt_text = StringField('Alt Text', validators=[Optional(), Length(max=255)])
    submit = SubmitField('Upload')

class MediaForm(FlaskForm):
    """Form for uploading media files"""
    image = FileField('Image File', validators=[
        FileRequired(),
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Images only!')
    ])
    image_type = SelectField('Image Type', choices=[
        ('featured', 'Featured Image'),
        ('content', 'Content Image')
    ], validators=[DataRequired()])
    alt_text = StringField('Alt Text', validators=[Length(max=255)])
    submit = SubmitField('Upload Image')

class LoginForm(FlaskForm):
    """User login form"""
    username = StringField('Username', validators=[DataRequired()])
    password = StringField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')

class PostForm(FlaskForm):
    """Form for creating and editing posts"""
    title = StringField('Title', validators=[DataRequired(), Length(min=3, max=255)])
    slug = StringField('Slug', validators=[DataRequired(), Length(min=3, max=255)])
    summary = TextAreaField('Summary', validators=[Optional(), Length(max=500)])
    content = TextAreaField('Content', validators=[DataRequired()])
    category_id = SelectField('Category', coerce=int)
    featured_image = FileField('Featured Image', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'webp'], 'Images only!')
    ])
    meta_description = StringField('Meta Description', validators=[Optional(), Length(max=255)])
    meta_keywords = StringField('Meta Keywords', validators=[Optional(), Length(max=255)])
    published = BooleanField('Publish')
    submit = SubmitField('Save')

class CategoryForm(FlaskForm):
    """Form for creating and editing categories"""
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=50)])
    slug = StringField('Slug', validators=[DataRequired(), Length(min=2, max=50)])
    submit = SubmitField('Save')

class TagForm(FlaskForm):
    """Form for creating and editing tags"""
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=50)])
    slug = StringField('Slug', validators=[DataRequired(), Length(min=2, max=50)])
    submit = SubmitField('Save')

class UserForm(FlaskForm):
    """Form for creating and editing users"""
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = StringField('Password', validators=[Optional(), Length(min=6)])
    is_admin = BooleanField('Admin')
    submit = SubmitField('Save')

class ContactForm(FlaskForm):
    """Form for contact page"""
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    subject = StringField('Subject', validators=[DataRequired(), Length(min=2, max=100)])
    message = TextAreaField('Message', validators=[DataRequired()])
    submit = SubmitField('Send Message')