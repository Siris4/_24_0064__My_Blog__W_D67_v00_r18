from flask import Flask, render_template, request, redirect, url_for, flash
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField
from wtforms.validators import DataRequired, URL, EqualTo, Email
from flask_ckeditor import CKEditor, CKEditorField
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import date
import datetime as dt
import requests
import re
import smtplib
import os
import logging

app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
Bootstrap5(app)
ckeditor = CKEditor(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

MY_NAME = 'Gavin "Siris" Martin'  # Defined globally for reuse in routes and/or functions

# Environment variables for email configuration
my_from_email1 = os.environ.get('MY_FROM_EMAIL1', 'Custom Message / Email does not exist')
password = os.environ.get('PASSWORD', 'Custom Message / Password does not exist')
their_email2 = os.environ.get('THEIR_EMAIL2', 'Custom Message / Email does not exist')

# CREATE DATABASE
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///posts.db'
db = SQLAlchemy(model_class=Base)
db.init_app(app)

# CONFIGURE TABLES
class BlogPost(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(String(250), nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)

class User(db.Model, UserMixin):
    id = mapped_column(Integer, primary_key=True)
    email = mapped_column(String(150), unique=True, nullable=False)
    password = mapped_column(String(60), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

# Context processor to inject variables into all templates
@app.context_processor
def inject_globals():
    return {
        'CURRENT_YEAR': dt.datetime.now().year,
        'MY_NAME': MY_NAME
    }

# Function to clean and slugify input strings
def slugify(value):
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    value = re.sub(r'[\s_-]+', '-', value)
    return value

app.jinja_env.filters['slugify'] = slugify

# Function to fetch posts and handle images based on post titles
def fetch_posts(limit=3):
    static_posts = [{"title": "All About Llamas", "subtitle": "One of the South American members of Camelidae",
                     "author": "Mojo Jojo", "date": "2023-09-24", "image": "llama.jpg",
                     "body": "The llama is the largest of the four lamoid species. It averages 120 cm (47 inches) at the shoulder, with most males weighing between 136 and 181.4 kg (300 and 400 pounds) and most females weighing between 104.3 and 158.7 kg (230 and 350 pounds). A 113-kg (250-pound) llama can carry a load of 45–60 kg and average 25 to 30 km (15 to 20 miles) travel a day. The llama’s high thirst tolerance, endurance, and ability to subsist on a wide variety of forage makes it an important transport animal on the bleak Andean plateaus and mountains. The llama is a gentle animal, but, when overloaded or maltreated, it will lie down, hiss, spit and kick, and refuse to move. Llamas breed in the (Southern Hemispheric) late summer and fall, from November to May. The gestation period lasts about 11 months, and the female gives birth to one young. Although usually white, the llama may be solid black or brown, or it may be white with black or brown markings."}]
    try:
        blog_url = "https://api.npoint.io/e52811763db21dfef489"
        blog_response = requests.get(blog_url)
        blog_response.raise_for_status()
        api_posts = blog_response.json()
        update_post_images(api_posts)
    except requests.RequestException as e:
        logging.error(f"Failed to retrieve blog data: {e}")
        api_posts = []
    return (static_posts + api_posts)[:limit]

def update_post_images(api_posts):
    for post in api_posts:
        post['date'] = dt.datetime.now().strftime("%b %d, %Y %I:%M%p")
        post['author'] = post.get('author', 'Dr. Angela Yu')
        post['image'] = post.get('image', 'default.jpg')
        if 'explore' in post['title'].lower():
            post['image'] = 'explore.jpg'
        elif 'heart' in post['title'].lower():
            post['image'] = 'heart2.jpg'
        elif 'science' in post['title'].lower():
            post['image'] = 'science.jpg'
        elif 'failure' in post['title'].lower():
            post['image'] = 'failure.jpg'

@app.route('/')
@app.route('/home')
def home():
    all_posts = fetch_posts(limit=3)
    all_posts.sort(key=lambda x: x['date'], reverse=True)
    return render_template("index.html", posts=all_posts, page='home')

@app.route('/post/<slug>')
def post(slug):
    all_posts = fetch_posts()
    post = next((p for p in all_posts if slugify(p['title']) == slug), None)
    if post is None:
        return "Post not found", 404
    return render_template("post.html", post=post)

@app.route('/about')
def about():
    return render_template('about.html', page='about')

@app.route('/contact', methods=["GET", "POST"])
def contact():
    form_submitted = False
    if request.method == "POST":
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        message = request.form.get('message')
        if validate_input(name, email, phone, message):
            send_email(name, email, phone, message)
            form_submitted = True
            logging.info(f"Contact form submitted: {name}, {email}")
        else:
            logging.warning("Validation failed for contact form submission.")
            return "Invalid input data", 400
    return render_template("contact.html", form_submitted=form_submitted)

def validate_input(name, email, phone, message):
    if not all([name, email, phone, message]):
        return False
    if "@" not in email or "." not in email:  # Simple email validation
        return False
    return True

def send_email(name, email, phone, message):
    """ Function to send email with contact details. """
    email_subject = "New Contact Form Submission for Siris's Blog"
    email_body = f"Subject:{email_subject}\n\nName: {name}\nEmail: {email}\nPhone: {phone}\nMessage: {message}"
    try:
        with smtplib.SMTP("smtp.gmail.com", port=587) as connection:
            connection.starttls()
            connection.login(user=my_from_email1, password=password)
            connection.sendmail(
                from_addr=my_from_email1,
                to_addrs=their_email2,
                msg=email_body
            )
        logging.info("Email sent successfully")
    except smtplib.SMTPException as e:
        logging.error(f"Failed to send email: {e}")

@app.route('/new-post', methods=["GET", "POST"])
@login_required
def add_new_post():
    form = RegisterForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            date=date.today().strftime("%B %d, %Y"),
            body=form.body.data,
            author=form.author.data,
            img_url=form.img_url.data
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("home"))
    return render_template("make-post.html", form=form)

@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@login_required
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    form = RegisterForm(
        title=post.title,
        subtitle=post.subtitle,
        body=post.body,
        author=post.author,
        img_url=post.img_url
    )
    if form.validate_on_submit():
        post.title = form.title.data
        post.subtitle = form.subtitle.data
        post.body = form.body.data
        post.author = form.author.data
        post.img_url = form.img_url.data
        db.session.commit()
        return redirect(url_for("post", slug=slugify(post.title)))
    return render_template("make-post.html", form=form, is_edit=True)

@app.route("/delete/<int:post_id>")
@login_required
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for("home"))

@app.route("/register", methods=["GET", "POST"])
def register():
    form = UserRegisterForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You can now log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', form=form)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))

if __name__ == "__main__":
    app.run(debug=True)
