from flask import Flask, request, render_template, jsonify,redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from flask import make_response
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import re
from flask import send_file
import io
import xlsxwriter
from werkzeug.security import generate_password_hash, check_password_hash
from flask import request, jsonify, session
import pandas as pd
app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'

db = SQLAlchemy(app)

###############################################################################
############################# Database Model ##################################
###############################################################################

class Setting(db.Model):
    setting_id = db.Column(db.Integer,primary_key=True)
    fine=db.Column(db.Integer,nullable=False)
    loan=db.Column(db.Integer,nullable=False)

class Member(db.Model):
    member_id = db.Column(db.Integer, primary_key=True)  # Remove autoincrement=True
    member_name = db.Column(db.String(100), nullable=False)
    member_email = db.Column(db.String(100))
    member_address = db.Column(db.String(100))
    member_class = db.Column(db.String(100), nullable=False)
    member_gender = db.Column(db.String(10), nullable=False)
    member_phone_number = db.Column(db.String(15))
    member_dob = db.Column(db.Date, nullable=False)
    member_date_created = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

class Librarian(db.Model):
    librarian_id = db.Column(db.Integer, primary_key=True)
    librarian_name = db.Column(db.String(100), nullable=False)
    librarian_date_created = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())  # Fixed name
    password = db.Column(db.String(255), nullable=False)

class Prefix(db.Model):
    prefix = db.Column(db.String(100), primary_key=True)
    prefix_name = db.Column(db.String(100), nullable=False)

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.String(100), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    language = db.Column(db.String(100),nullable=False)
    page = db.Column(db.Integer, default=1)
    price = db.Column(db.Integer, nullable=True)
    prefix_id = db.Column(db.String(100), db.ForeignKey('prefix.prefix'), nullable=False)
    
    # Relationships
    prefix = db.relationship('Prefix', backref=db.backref('books', lazy=True))
    
    def __repr__(self):
        return f"<Book {self.book_id} - {self.title}>"

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.String(100), db.ForeignKey('book.book_id'), nullable=False)
    member_id = db.Column(db.String(100), db.ForeignKey('member.member_id'), nullable=False)
    issue_date = db.Column(db.Date, default=datetime.utcnow, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    return_date = db.Column(db.Date, nullable=True)
    fine = db.Column(db.Integer, default=0)

    # Relationships
    book = db.relationship('Book', backref=db.backref('transactions', lazy=True))
    member = db.relationship('Member', backref=db.backref('transactions', lazy=True))

    def calculate_fine(self):
        if self.return_date and self.return_date > self.due_date:
            days_late = (self.return_date - self.due_date).days
            self.fine = days_late * 5
        else:
            self.fine = 0
# Ensure database tables exist before modifying the sequence
with app.app_context():
    db.create_all()  # CREATE DATABASE TABLES FIRST

    # Check if `sqlite_sequence` table exists before updating it
    table_exists = db.session.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence';"
    )).fetchone()

    if table_exists:
        result = db.session.execute(text("SELECT seq FROM sqlite_sequence WHERE name = 'member'")).fetchone()
        if result is None or result[0] < 999:
            db.session.execute(text("UPDATE sqlite_sequence SET seq = 999 WHERE name = 'member'"))
            db.session.commit()

###############################################################################

###############################################################################
################################ MAIN PAGE ####################################
###############################################################################

@app.route('/')
def index():
    return render_template('index.html')

###############################################################################
###################### MEMBER REGISTRATION ####################################
###############################################################################

@app.route('/memberregistration', methods=['GET', 'POST'])
def member_registration():
    new_member_id = None  # Default to None

    if request.method == 'POST':
        try:
            member_name = request.form.get('fullName')
            email = request.form.get('email')
            address = request.form.get('address')
            mem_class = request.form.get('class')
            phone = request.form.get('phone')
            gender = request.form.get('gender')
            dob = request.form.get('dob')
            if not (member_name and email and phone and gender and dob):
                flash("All fields are required!", "error")
                return redirect(url_for('member_registration'))

            # Convert DOB to date object
            dob = datetime.strptime(dob, "%Y-%m-%d").date()

            # Get the latest member_id and assign the next ID
            last_member = Member.query.order_by(Member.member_id.desc()).first()
            new_member_id = 2001 if not last_member else last_member.member_id + 1

            # Insert into database
            new_member = Member(
                member_id=new_member_id,  # Manually set member_id
                member_name=member_name,
                member_email=email,
                member_address=address,
                member_class=mem_class,
                member_phone_number=phone,
                member_gender=gender,
                member_dob=dob,
            )
            db.session.add(new_member)
            db.session.commit()

            flash(f"Registration successful! Your Member ID is {new_member_id}.", "success")

        except Exception as e:
            print("Error:", str(e))
            flash("An error occurred while registering. Please try again.", "error")

    return render_template('librarian/memberregister.html', member_id=new_member_id)
###############################################################################
###################### dashboard ##############################################
###############################################################################
@app.route('/librariandashboard')
def librariandashboard():
    if 'librarian_id' in session:
        librarian = Librarian.query.get(session['librarian_id'])
        response = make_response(render_template('librarian/dashboard.html', librarian_name=librarian.librarian_name))
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    flash("Please log in first.", "error")
    return redirect(url_for('lib_login'))

from flask import jsonify

@app.route('/get_transactions')
def get_transactions():
    transactions = Transaction.query.all()
    transaction_data = []  # Initialize the list

    for transaction in transactions:
        transaction_data.append({
            "transaction_id": transaction.member.member_id,
            "member_name": transaction.member.member_name if transaction.member else "Unknown",
            "book_id":transaction.book.book_id,
            "book_title": transaction.book.title if transaction.book else "Unknown",
            "issue_date": transaction.issue_date.strftime("%Y-%m-%d"),
            "return_date": transaction.return_date.strftime("%Y-%m-%d") if transaction.return_date else None,
            "due_date": transaction.due_date.strftime("%Y-%m-%d"),
            "fine": transaction.fine,
            "status": "Returned" if transaction.return_date else "Issued"
        })

    return jsonify({"success": True, "transactions": transaction_data})



###############################################################################
###################### LIBRARIAN LOGIN & REGISTRATION #########################
###############################################################################

@app.route('/librarianregistration', methods=['GET', 'POST'])
def lib_reg():
    print("in librarianregistration")
    if request.method == 'POST':
        try:
            librarian_name = request.form.get('fullName')
            password = request.form.get('password')
            
            if not (librarian_name and password):
                flash("All fields are required!", "error")
                return redirect(url_for('lib_reg'))

            # Hash the password
            password_hash = generate_password_hash(password)

            # Create new librarian entry
            new_librarian = Librarian(
                librarian_name=librarian_name,
                password=password_hash
            )
            db.session.add(new_librarian)
            db.session.commit()

            flash("Librarian registration successful!", "success")
            return redirect(url_for('lib_login'))  # Redirect to librarian login

        except Exception as e:
            print("Error:", str(e))
            flash("An error occurred while registering. Please try again.", "error")

    return render_template('librarian/register.html')


@app.route('/librarianlogin', methods=['GET', 'POST'])
def lib_login():
    if request.method == 'POST':
        libname = request.form.get('libname')  # Get librarian name
        password = request.form.get('password')

        print("Login attempt:", libname, password)  # Debugging

        # Fetch the librarian by name
        librarian = Librarian.query.filter_by(librarian_name=libname).first()
        print("Fetched Librarian:", librarian)
        
        if librarian:
            print("Stored password hash:", librarian.password)  # Debugging stored hash
            if check_password_hash(librarian.password, password):
                session['librarian_id'] = librarian.librarian_id  # Store session
                flash("Login successful!", "success")
                print("in daashboardd")
                return redirect(url_for('librariandashboard'))
            else:
                flash("Wrong username or password", "error")
        else:
            flash("No account found with that username.", "error")

    return render_template('librarian/login.html')

###############################################################################
############################ LOGOUT ###########################################
###############################################################################
@app.route('/logout')
def logout():
    session.pop('member_id', None)  # Remove member session
    session.pop('librarian_id', None)  # Remove librarian session
    flash("You have been logged out.", "success")

    response = make_response(redirect(url_for('index')))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    return response
###############################################################################
######################## BOOK SECTION #########################################
###############################################################################
@app.route('/additem')
def additem():

      # Fetching distinct prefix names from the Prefix table
    prefixes = db.session.query(Prefix.prefix).distinct().all()
    prefix_list = [prefix_name[0] for prefix_name in prefixes]  # Extract prefix names

    categories = db.session.query(Prefix.prefix_name).distinct().all()
    category_list = [prefix_name[0] for prefix_name in categories]  # Extract category names
    return render_template('librarian/additem.html', prefixes=prefix_list)

@app.route('/catlog')
def catlog():
    # Query all books
    books = Book.query.all()

    # Initialize a list to store book details with availability
    book_details = []

    for book in books:
        # Check if the book has a related transaction where return_date is None
        active_transaction = Transaction.query.filter_by(book_id=book.book_id, return_date=None).first()

        # If there is an active transaction, the book is unavailable
        if active_transaction:
            availability = "Unavailable"
        else:
            availability = "Available"

        # Add book details along with availability
        book_details.append({
            "book_id": book.book_id,
            "title": book.title,
            "author": book.author,
            "language": book.language,
            "category": book.category,
            "availability": availability
        })

    # Pass the book details to the template
    return render_template('librarian/catlog.html', book_details=book_details)



@app.route('/transaction')
def transaction():
    return render_template('librarian/transaction.html')
###############################################################################
###################### MEMBER SECTION #########################################
###############################################################################

@app.route('/viewmember')
def viewmember():
    # Query all books
    members = Member.query.all()


    # Pass the book details to the template
    return render_template('librarian/viewmember.html', member_details=members)



###############################################################################
###################### SETTING SECTION #########################################
###############################################################################

@app.route('/setting')
def setting():
    # Assuming you have a Settings table with a fine column
    fine_value = db.session.query(Setting.fine).first()
    loan_value= db.session.query(Setting.loan).first()
    # If fine_value exists, get the first element; otherwise, set default
    fine_value = fine_value[0] if fine_value else 0  
    loan_value = loan_value[0] if loan_value else 0  
    
    return render_template('librarian/setting.html', fine_value=fine_value,loan_value=loan_value)

@app.route('/update_fine', methods=['POST'])
def update_fine():
    fine_value = request.json.get('fine')  # Get fine value from request body

    if fine_value is None or fine_value == "":
        return jsonify({"error": "Fine value is required"}), 400

    try:
        fine_value = int(fine_value)  # Convert to integer
        setting = Setting.query.first()  # Get the first row from the setting table

        if setting:
            setting.fine = fine_value  # Update only the fine column
        else:
            setting = Setting(fine=fine_value, loan=0)  # Ensure loan has a default value
            db.session.add(setting)

        db.session.commit()
        return jsonify({"success": True, "message": "Fine updated successfully!"})

    except ValueError:
        return jsonify({"error": "Invalid fine value"}), 400

@app.route('/update_loan', methods=['POST'])
def update_loan():
    loan_value = request.json.get('loan')  # Get fine value from request body

    if loan_value is None or loan_value == "":
        return jsonify({"error": "loan value is required"}), 400

    try:
        loan_value = int(loan_value)  # Convert to integer
        setting = Setting.query.first()  # Get the first row from the setting table

        if setting:
            setting.loan = loan_value  # Update only the fine column
        else:
            setting = Setting(fine=0, loan=loan_value)  # Ensure loan has a default value
            db.session.add(setting)

        db.session.commit()
        return jsonify({"success": True, "message": "Fine updated successfully!"})

    except ValueError:
        return jsonify({"error": "Invalid fine value"}), 400
# Endpoint to check if prefix exists
@app.route('/check_prefix/<prefix>', methods=['GET'])
def check_prefix(prefix):
    existing_prefix = Prefix.query.filter_by(prefix=prefix).first()
    if existing_prefix:
        return jsonify({'exists': True})
    else:
        return jsonify({'exists': False})

# Endpoint to add a new prefix
@app.route('/addprefix', methods=['POST'])
def add_prefix():
    data = request.get_json()
    prefix = data.get('prefix')
    prefix_full_name = data.get('prefix_full_name')
    
    if Prefix.query.filter_by(prefix=prefix).first():
        return jsonify({'success': False, 'message': 'Prefix already exists'})

    new_prefix = Prefix(prefix=prefix, prefix_name=prefix_full_name)
    db.session.add(new_prefix)
    db.session.commit()

    return jsonify({'success': True})

@app.route('/get_next_book_id/<prefix>')
def get_next_book_id(prefix):
    # Retrieve all books that match the given prefix
    books = db.session.execute(
        text("SELECT book_id FROM book WHERE book_id LIKE :prefix"),
        {"prefix": f"{prefix}%"}
    ).fetchall()

    # If there are no books, start the numbering from 1
    if books:
        # Extract the numeric part of the book_ids and store them in a list
        book_numbers = []
        for book in books:
            last_id = book[0]  # Extract book_id (e.g., ELT7)
            number_part = int(last_id[len(prefix):])  # Extract numeric part
            book_numbers.append(number_part)

        # Find the maximum number and increment it
        next_number = max(book_numbers) + 1
    else:
        next_number = 1  # Start from 1 if no records exist

    return jsonify({"next_book_id": f"{prefix}{next_number}"})


@app.route('/add_book', methods=['POST'])
def add_book():
    try:
        data = request.json  # Get JSON data from frontend
        print(data)
        # Extract data
        book_id = data.get('book_id')
        title = data.get('title')
        author = data.get('author')
        category = data.get('category')
        language = data.get('language')
        page = int(data.get('page', 100))  # Default to 1 if missing
        price = data.get('price')
        prefix_id = data.get('prefix_id')

        # Validate required fields
# Validate required fields
        if not book_id:
            return jsonify({"error": "Missing book_id"}), 400
        if not title:
            return jsonify({"error": "Missing title"}), 400
        if not author:
            return jsonify({"error": "Missing author"}), 400
        if not category:
            return jsonify({"error": "Missing category"}), 400
        if not prefix_id:
            return jsonify({"error": "Missing prefix_id"}), 400

# Proceed with other logic if all fields are present


        # Check if book_id already exists
        existing_book = Book.query.filter_by(book_id=book_id).first()
        if existing_book:
            return jsonify({"error": "Book ID already exists"}), 409  # Conflict

        # Create new book entry
        new_book = Book(
            book_id=book_id,
            title=title,
            author=author,
            category=category,
            language = language,
            page=page,
            price=price,
            prefix_id=prefix_id
        )

        db.session.add(new_book)
        db.session.commit()

        return jsonify({"message": "Book added successfully"}), 201  # Created

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500  # Internal Server Error
@app.route('/get_member_details/<member_id>', methods=['GET'])
def get_member_details(member_id):
    # Get the loan limit from settings
    loan_value = db.session.query(Setting.loan).first()
    loan_value = loan_value[0] if loan_value else 0  

    # Get the member details
    member = Member.query.filter_by(member_id=member_id).first()
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Count books currently issued (return_date = NULL)
    issued_books_count = Transaction.query.filter_by(member_id=member_id, return_date=None).count()
    if (issued_books_count > loan_value):
        allowance = False
    else:
        allowance = True

    return jsonify({
        'name': member.member_name,
        'email': member.member_email,
        'books_allowed': allowance  # Number of books currently issued
    })

@app.route('/get_categories_by_prefix/<prefix>', methods=['GET'])
def get_categories_by_prefix(prefix):
    # Fetch the categories that correspond to the selected prefix
    categories = db.session.query(Prefix.prefix_name).filter(Prefix.prefix == prefix).all()
    category_list = [category[0] for category in categories]  # Extract category names
    return jsonify({'categories': category_list})

@app.route('/get_book_details/<book_id>', methods=['GET'])
def get_book_details(book_id):

    # Normalize input: uppercase prefix + numeric part with no leading zeros
    prefix = ''.join(filter(str.isalpha, book_id)).upper()
    numeric_part = ''.join(filter(str.isdigit, book_id))
    numeric_part = str(int(numeric_part)) if numeric_part else "0"
    normalized_id = f"{prefix}{numeric_part}"

    # Get all book IDs from the database
    bookid_data = db.session.query(Book.book_id).all()

    matched_id = None
    for (bid,) in bookid_data:
        db_prefix = ''.join(filter(str.isalpha, bid)).upper()
        db_numeric = ''.join(filter(str.isdigit, bid))
        db_numeric = str(int(db_numeric)) if db_numeric else "0"
        normalized_db_id = f"{db_prefix}{db_numeric}"

        if normalized_db_id == normalized_id:
            matched_id = bid  # original database ID
            break

    if not matched_id:
        return jsonify({'error': 'Book not found'}), 404

    # Get the book using the matched original ID
    book = Book.query.filter_by(book_id=matched_id).first()

    # Check if the book has any active (not returned) transactions
    active_transaction = Transaction.query.filter_by(book_id=matched_id, return_date=None).first()

    # Determine availability status
    book_available = False if active_transaction else True

    return jsonify({
        'book_id': matched_id.upper(),  # Ensure the response is in uppercase
        'title': book.title,
        'author': book.author,
        'category': book.category,
        'available': book_available
    })

    return jsonify({
        'title': book.title,
        'author': book.author,
        'category': book.category,
        'available': book_available
    })


@app.route('/process_transaction', methods=['POST'])
def process_transaction():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data received"}), 400

        print("Received Data:", data)

        transaction_type = data.get('transactionType')
        member_id = data.get('memberId')
        book_id = data.get('bookId')
        due_date_str = data.get('dueDate')

        if transaction_type == "issue":
            if not due_date_str:
                return jsonify({"error": "Due date is required for issuing a book"}), 400

            due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            transaction = Transaction(
                book_id=book_id,
                member_id=member_id,
                issue_date=datetime.utcnow().date(),
                due_date=due_date
            )
            db.session.add(transaction)

        elif transaction_type == "return":
            transaction = Transaction.query.filter_by(book_id=book_id, member_id=member_id, return_date=None).first()
            if not transaction:
                return jsonify({"error": "No active issue record found for this book"}), 400

            transaction.return_date = datetime.now().date()
            transaction.calculate_fine()

        else:
            return jsonify({"error": "Invalid transaction type"}), 400

        db.session.commit()
        return jsonify({"success": "Transaction processed successfully!"})

    except ValueError as e:
        print("ValueError:", str(e))
        return jsonify({"error": f"Invalid date format: {str(e)}"}), 400
    except Exception as e:
        print("General Error:", str(e))
        return jsonify({"error": str(e)}), 500

@app.route('/change_password', methods=['POST'])
def change_password():
    data = request.get_json()  # Get the form data from the frontend
    
    current_password = data.get('current_password')
    new_password = data.get('new_password')

    # Get the librarian's ID from the session
    librarian_id = session.get('librarian_id')
    librarian = Librarian.query.get(librarian_id)

    if librarian:
        # Check if the current password is correct
        if check_password_hash(librarian.password, current_password):
            # If correct, update the password
            librarian.password = generate_password_hash(new_password)
            db.session.commit()  # Commit the change to the database
            
            # Include librarian's name in the success response
            return jsonify({'success': True, 'message': f"Password changed successfully for {librarian.librarian_name}!"})
        else:
            return jsonify({'success': False, 'error': 'Current password is incorrect'})
    else:
        return jsonify({'success': False, 'error': 'Librarian not found'})

@app.route('/datamanage')
def data_manage():
    return render_template('librarian/datamanagement.html')

# Export endpoints
@app.route('/export/prefix')
def export_prefix():
    prefixes = Prefix.query.all()
    df = pd.DataFrame([{'prefix': p.prefix, 'prefix_name': p.prefix_name} for p in prefixes])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='prefix')
    output.seek(0)
    return send_file(output, download_name='prefix_data.xlsx', as_attachment=True)

@app.route('/export/members')
def export_members():
    members = Member.query.all()
    df = pd.DataFrame([{
        'member_id': m.member_id,
        'member_name': m.member_name,
        'member_email': m.member_email,
        'member_address': m.member_address,
        'member_class': m.member_class,
        'member_gender': m.member_gender,
        'member_phone_number': m.member_phone_number,
        'member_dob': m.member_dob,
        'member_date_created': m.member_date_created
    } for m in members])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='members')
    output.seek(0)
    return send_file(output, download_name='member_data.xlsx', as_attachment=True)

@app.route('/export/books')
def export_books():
    books = Book.query.all()
    df = pd.DataFrame([{
        'book_id': b.book_id,
        'title': b.title,
        'author': b.author,
        'category': b.category,
        'language': b.language,
        'page': b.page,
        'price': b.price,
        'prefix_id': b.prefix_id
    } for b in books])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='books')
    output.seek(0)
    return send_file(output, download_name='book_data.xlsx', as_attachment=True)

# Import endpoint (all sheets)
@app.route('/import', methods=['POST'])
def import_data():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if not file.filename.endswith('.xlsx'):
        return jsonify({'error': 'Invalid file type'}), 400

    try:
        xls = pd.read_excel(file, sheet_name=None)
        with app.app_context():
            # Prefix
            if 'prefix' in xls:
                for _, row in xls['prefix'].iterrows():
                    prefix = Prefix.query.filter_by(prefix=row['prefix']).first()
                    if not prefix:
                        prefix = Prefix(prefix=row['prefix'])
                        db.session.add(prefix)
                    prefix.prefix_name = row['prefix_name']

            # Members
            if 'members' in xls:
                for _, row in xls['members'].iterrows():
                    member = Member.query.filter_by(member_id=row['member_id']).first()
                    if not member:
                        member = Member(member_id=row['member_id'])
                        db.session.add(member)
                    member.member_name = row['member_name']
                    member.member_email = row['member_email']
                    member.member_address = row['member_address']
                    member.member_class = row['member_class']
                    member.member_gender = row['member_gender']
                    member.member_phone_number = str(row['member_phone_number'])
                    member.member_dob = pd.to_datetime(row['member_dob']).date()
                    member.member_date_created = pd.to_datetime(row['member_date_created'])

            # Books
            if 'books' in xls:
                for _, row in xls['books'].iterrows():
                    prefix_exists = Prefix.query.filter_by(prefix=row["prefix_id"]).first()
                    if not prefix_exists:
                        continue
                    book = Book.query.filter_by(book_id=row['book_id']).first()
                    if not book:
                        book = Book(book_id=row['book_id'])
                        db.session.add(book)
                    book.title = row['title']
                    book.author = row['author']
                    book.category = row['category']
                    book.language = row['language']
                    book.page = row['page']
                    book.price = row['price']
                    book.prefix_id = row['prefix_id']

            db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
if __name__ == '__main__':
    app.run(debug=True)
