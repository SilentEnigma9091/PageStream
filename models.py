from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from datetime import datetime


db = SQLAlchemy()
bcrypt = Bcrypt()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)  # <- This is the problem
    password_hash = db.Column(db.String(128), nullable=False)

    # New profile fields
    name = db.Column(db.String(120))
    birthdate = db.Column(db.String(10))  # Format: YYYY-MM-DD
    gender = db.Column(db.String(10))
    profile_pic = db.Column(db.String(200)) 

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)
    
class BookPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    author = db.Column(db.String(100))
    description = db.Column(db.Text)
    genre = db.Column(db.String(50))
    book_file = db.Column(db.String(200))  # filename of uploaded book
    image_file = db.Column(db.String(200))  # cover image
    timestamp = db.Column(db.DateTime, server_default=db.func.now())
    price = db.Column(db.Float, nullable=True, default=9.99)  # Adding price field with default

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('posts', lazy=True))

    # ADD THIS LINE to cascade delete comments with the post
    comments = db.relationship('Comment', backref='post', cascade='all, delete-orphan', lazy=True)


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('book_post.id', ondelete='CASCADE'), nullable=False)

    user = db.relationship('User', backref=db.backref('comments', lazy=True))


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book_post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    total_price = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    book = db.relationship('BookPost', backref='orders')
    user = db.relationship('User', backref='orders')
