import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from models import db, bcrypt, User,BookPost,Comment,Order
from sqlalchemy import event, or_, asc, desc
from sqlalchemy.engine import Engine
import sqlite3
from functools import wraps
from collections import defaultdict

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Configs
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Init extensions
db.init_app(app)
bcrypt.init_app(app)

# Create tables
with app.app_context():
    db.create_all()
    
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
        
@app.route('/')
def home():
    featured_books = BookPost.query.order_by(BookPost.timestamp.asc()).limit(4).all()
    return render_template('home.html', BookPost=BookPost)

@app.route('/home_page')
def home_page(): 
    featured_books = BookPost.query.order_by(BookPost.timestamp.asc()).limit(4).all()
    return render_template('home.html', BookPost=BookPost)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')

        # Basic checks
        if not email:
            flash('Email is required.', 'error')
            return redirect(url_for('signup'))

        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'error')
            return redirect(url_for('signup'))
        if User.query.filter_by(email=email).first():
            flash('Email already in use.', 'error')
            return redirect(url_for('signup'))

        if password != confirm:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('signup'))

        # Create user with email
        new_user = User(username=username, email=email)
        new_user.set_password(password)

        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {e}', 'error')
            return redirect(url_for('signup'))

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()  # Can be username or email
        password = request.form.get('password', '')

        # Try finding user by username or email
        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier)
        ).first()

        if user and user.check_password(password):
            session['username'] = user.username  # Store the actual username
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials.', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/delete_account', methods=['POST'])
def delete_account():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user = User.query.filter_by(username=session['username']).first()
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        # Get all posts by the user
        posts = BookPost.query.filter_by(user_id=user.id).all()
        
        # Delete all comments on user's posts
        for post in posts:
            Comment.query.filter_by(post_id=post.id).delete()
        
        # Delete all user's posts
        BookPost.query.filter_by(user_id=user.id).delete()
        
        # Delete all comments made by the user
        Comment.query.filter_by(user_id=user.id).delete()
        
        # Delete the user
        db.session.delete(user)
        db.session.commit()
        
        # Clear session
        session.clear()
        flash('Your account has been deleted successfully.', 'success')
        return redirect(url_for('home'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting account: {e}', 'error')
        return redirect(url_for('dashboard'))

@app.route('/dashboard', methods=['GET'])
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session['username']).first()
    
    # Get user's books
    user_books = BookPost.query.filter_by(user_id=user.id).all()
    
    # Get user's orders
    orders = Order.query.filter_by(user_id=user.id).all()
    
    # Get user sales (orders for books posted by the user)
    sales = []
    for book in user_books:
        book_orders = Order.query.filter_by(book_id=book.id).all()
        sales.extend(book_orders)
    
    # Calculate statistics
    total_books = len(user_books)
    total_orders = len(orders)
    total_sales = len(sales)
    
    # Calculate total money spent and earned
    money_spent = sum(order.total_price for order in orders)
    money_earned = sum(sale.total_price for sale in sales)
    
    return render_template('dashboard.html', 
                          user=user, 
                          books=user_books,
                          orders=orders, 
                          sales=sales,
                          total_books=total_books,
                          total_orders=total_orders,
                          total_sales=total_sales,
                          money_spent=money_spent,
                          money_earned=money_earned)
@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'username' not in session:
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session['username']).first()

    if request.method == 'POST':
        file = request.files['profile_pic']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            user.profile_pic = filename

        user.name = request.form['name']
        user.gender = request.form['gender']
        user.birthdate = request.form['birthdate']
        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('edit_profile.html', user=user) # Assuming 'home.html' is your homepage template
@app.route('/post_book', methods=['GET', 'POST'])
def post_book():
    if 'username' not in session:
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session['username']).first()

    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        description = request.form['description']
        price = float(request.form.get('price', 9.99))
        genre = request.form['genre']
        book_file = request.files['book_file']
        image_file = request.files['image_file']

        book_filename = ''
        image_filename = ''
        if book_file and allowed_file(book_file.filename):
            book_filename = secure_filename(book_file.filename)
            book_file.save(os.path.join(app.config['UPLOAD_FOLDER'], book_filename))
        if image_file and allowed_file(image_file.filename):
            image_filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))

        post = BookPost(
            title=title,
            author=author,
            description=description,
            price=price,
            genre=genre,
            book_file=book_filename,
            image_file=image_filename,
            user=user
        )
        db.session.add(post)
        db.session.commit()
        flash('Book posted successfully!', 'success')
        return redirect(url_for('view_books'))

    return render_template('post_book.html')

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query', '')
    genre = request.args.get('genre', '')
    author = request.args.get('author', '')
    sort_by = request.args.get('sort_by', 'timestamp')
    sort_order = request.args.get('sort_order', 'desc')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)

    # Basic filtering and search logic
    search_query = BookPost.query
    if query:
        search_query = search_query.filter(
            or_(
                BookPost.title.contains(query),
                BookPost.description.contains(query),
                BookPost.author.contains(query)
            )
        )
    if genre and genre != "All":
        search_query = search_query.filter(BookPost.genre == genre)
    if author and author != "All":
        search_query = search_query.filter(BookPost.author == author)

    # Add price range filtering
    if min_price is not None:
        search_query = search_query.filter(BookPost.price >= min_price)
    if max_price is not None:
        search_query = search_query.filter(BookPost.price <= max_price)


    # Sorting
    if sort_order == 'asc':
        search_query = search_query.order_by(asc(getattr(BookPost, sort_by)))
    else:
        search_query = search_query.order_by(desc(getattr(BookPost, sort_by)))

    posts = search_query.all()

    # Get unique genres and authors for filters
    genres = db.session.query(BookPost.genre).distinct().all()
    authors = db.session.query(BookPost.author).distinct().all()

    return render_template(
        'view_books.html', 
        posts=posts, 
        genres=genres, 
        authors=authors, 
        search_query=query,
        selected_genre=genre,
        selected_author=author,
        selected_sort_by=sort_by,
        selected_sort_order=sort_order,
        min_price=min_price,
        max_price=max_price,
        is_search_result=True
    )

@app.route('/place_order/<int:post_id>', methods=['GET', 'POST'])
def place_order(post_id):
    if 'username' not in session:
        flash('Please login to place an order.', 'error')
        return redirect(url_for('login'))

    post = BookPost.query.get_or_404(post_id)
    user = User.query.filter_by(username=session['username']).first()

    if request.method == 'POST':
        quantity = int(request.form.get('quantity', 1))
        # Use the book's actual price from the database
        price = post.price  # Get the actual book price
        total_price = price * quantity

        new_order = Order(
            book_id=post.id,
            user_id=user.id,
            quantity=quantity,
            total_price=total_price
        )
        db.session.add(new_order)
        db.session.commit()

        flash('Order placed successfully!', 'success')
        return redirect(url_for('my_orders'))

    return render_template('order_confirmation.html', post=post)

@app.route('/my_orders')
def my_orders():
    if 'username' not in session:
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session['username']).first()
    orders = Order.query.filter_by(user_id=user.id).all()

    return render_template('my_orders.html', orders=orders)

@app.route('/my_sales')
def my_sales():
    if 'username' not in session:
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session['username']).first()
    
    # Get all books posted by the user
    user_books = BookPost.query.filter_by(user_id=user.id).all()
    
    # Get all orders for those books
    sales = []
    for book in user_books:
        book_orders = Order.query.filter_by(book_id=book.id).all()
        sales.extend(book_orders)
    
    return render_template('my_sales.html', sales=sales)


@app.route('/books')
def view_books():
    sort_by = request.args.get('sort_by', 'timestamp')
    sort_order = request.args.get('sort_order', 'desc')
    
    # Get unique genres and authors for filters
    genres = db.session.query(BookPost.genre).distinct().all()
    authors = db.session.query(BookPost.author).distinct().all()
    
    # Apply sorting
    if sort_order == 'asc':
        posts = BookPost.query.order_by(asc(getattr(BookPost, sort_by))).all()
    else:
        posts = BookPost.query.order_by(desc(getattr(BookPost, sort_by))).all()
    
    return render_template(
        'view_books.html', 
        posts=posts,
        genres=genres,
        authors=authors,
        selected_sort_by=sort_by,
        selected_sort_order=sort_order,
        is_search_result=False
    )

@app.route('/book/<int:post_id>', methods=['GET', 'POST'])
def book_detail(post_id):
    post = BookPost.query.get_or_404(post_id)
    user = User.query.filter_by(username=session['username']).first() if 'username' in session else None

    if request.method == 'POST' and user:
        content = request.form['comment']
        comment = Comment(content=content, user=user, post=post)
        db.session.add(comment)
        db.session.commit()
        flash('Comment added!', 'success')
        return redirect(url_for('book_detail', post_id=post.id))

    return render_template('book_detail.html', post=post)

@app.route('/delete_post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    post = BookPost.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    flash('Post and its comments deleted.', 'success')
    return redirect(url_for('dashboard'))

# Main admin route
@app.route('/admin')
def admin():
    # Check if admin is logged in
    if 'admin' in session:
        # Admin is logged in, redirect to dashboard
        return redirect(url_for('admin_dashboard'))
    else:
        # Admin is not logged in, redirect to login page
        return redirect(url_for('admin_login'))

# Admin login route
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Hard-coded admin credentials
        if username == 'admin' and password == 'admin':
            session['admin'] = True
            flash('Admin logged in successfully', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin credentials', 'error')
    
    return render_template('admin_login.html')

# Admin authentication middleware function
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin' not in session:
            flash('Admin access required', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin dashboard route
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    # Get stats for admin dashboard
    total_users = User.query.count()
    total_books = BookPost.query.count()
    total_orders = Order.query.count()
    
    # Get the latest users, books and orders to display in the dashboard
    latest_users = User.query.order_by(User.id.desc()).limit(5).all()
    latest_books = BookPost.query.order_by(BookPost.id.desc()).limit(5).all()
    latest_orders = Order.query.order_by(Order.id.desc()).limit(5).all()
    
    return render_template('admin_dashboard.html', 
                          total_users=total_users,
                          total_books=total_books,
                          total_orders=total_orders,
                          latest_users=latest_users,
                          latest_books=latest_books,
                          latest_orders=latest_orders,
                          User=User,  # Pass the User model to the template
                          BookPost=BookPost,  # Pass the BookPost model to the template
                          Order=Order)  # Pass the Order model to the template

# Admin users management route
@app.route('/admin/users')
@admin_required
def admin_users():
    # Get search parameter if it exists
    search = request.args.get('search', '')
    
    if search:
        # Filter users based on search term
        users = User.query.filter(
            (User.username.contains(search)) | 
            (User.email.contains(search))
        ).all()
    else:
        # Get all users
        users = User.query.all()

    user_books_count = defaultdict(int)
    for user in users:
        user_books_count[user.id] = BookPost.query.filter_by(user_id=user.id).count()

    
    return render_template('admin_users.html', users=users, Order=Order, user_books_count=user_books_count)

# Admin delete user route
@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    try:
        # Get all posts by the user
        posts = BookPost.query.filter_by(user_id=user.id).all()
        
        # Delete all comments on user's posts
        for post in posts:
            Comment.query.filter_by(post_id=post.id).delete()
        
        # Delete all user's posts
        BookPost.query.filter_by(user_id=user.id).delete()
        
        # Delete all comments made by the user
        Comment.query.filter_by(user_id=user.id).delete()
        
        # Delete all orders made by the user
        Order.query.filter_by(user_id=user.id).delete()
        
        # Delete the user
        db.session.delete(user)
        db.session.commit()
        
        flash('User deleted successfully', 'success')
        return redirect(url_for('admin_users'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {e}', 'error')
        return redirect(url_for('admin_users'))

# Admin books management route
@app.route('/admin/books')
@admin_required
def admin_books():
    # Get search parameter if it exists
    search = request.args.get('search', '')
    
    if search:
        # Filter books based on search term
        books = BookPost.query.filter(
            (BookPost.title.contains(search)) | 
            (BookPost.author.contains(search))
        ).all()
    else:
        # Get all books
        books = BookPost.query.all()
    
    return render_template('admin_books.html', books=books)

# Admin delete book route
@app.route('/admin/books/delete/<int:book_id>', methods=['POST'])
@admin_required
def admin_delete_book(book_id):
    book = BookPost.query.get_or_404(book_id)
    
    try:
        # Delete comments on the book
        Comment.query.filter_by(post_id=book.id).delete()
        
        # Delete orders for the book
        Order.query.filter_by(book_id=book.id).delete()
        
        # Delete the book
        db.session.delete(book)
        db.session.commit()
        
        flash('Book deleted successfully', 'success')
        return redirect(url_for('admin_books'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting book: {e}', 'error')
        return redirect(url_for('admin_books'))

# Admin orders management route
@app.route('/admin/orders')
@admin_required
def admin_orders():
    # Get search parameter if it exists
    search = request.args.get('search', '')
    
    if search:
        # Filter orders based on search term (user's username or book title)
        orders = Order.query.join(User).join(BookPost).filter(
            (User.username.contains(search)) | 
            (BookPost.title.contains(search))
        ).all()
    else:
        # Get all orders
        orders = Order.query.all()
    
    return render_template('admin_orders.html', orders=orders)

# Admin logout route
@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    flash('Admin logged out successfully', 'success')
    return redirect(url_for('admin_login'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
