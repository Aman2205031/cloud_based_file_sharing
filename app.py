from dotenv import load_dotenv
load_dotenv()

import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from authlib.integrations.flask_client import OAuth
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta
import sqlite3

# ---------- Flask App Configuration ----------
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecretkey")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), "uploads")
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ---------- Email (Optional) ----------
app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_DEFAULT_SENDER=os.getenv("MAIL_USERNAME")
)
mail = Mail(app)

# ---------- Login Manager ----------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# ---------- Bcrypt ----------
bcrypt = Bcrypt(app)

# ---------- OAuth ----------
oauth = OAuth(app)
oauth.register(
   name='microsoft',
    client_id='34411a6f-7685-468c-bcd5-12982595d034',  # Replace with your Microsoft client ID
    client_secret='QpN8Q~52Ef3Qt0_RwhLlNrWKpd93JeyGizSh1dAY',  # Replace with your Microsoft client secret
    server_metadata_url='https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# ---------- Azure Storage Config ----------
AZURE_STORAGE_ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
AZURE_STORAGE_ACCOUNT_KEY = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
AZURE_CONTAINER_NAME = "user-files"

blob_service_client = BlobServiceClient(
    account_url=f"https://{AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net",
    credential=AZURE_STORAGE_ACCOUNT_KEY
)
container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)

# ---------- User Loader ----------
class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, username FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return User(*row) if row else None

# ---------- Routes ----------
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = bcrypt.generate_password_hash(request.form["password"]).decode("utf-8")
        try:
            with sqlite3.connect("users.db") as conn:
                conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
                flash("✅ Registration successful!", "success")
                return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("❌ Username already exists!", "danger")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username, password = request.form["username"], request.form["password"]
        with sqlite3.connect("users.db") as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, password FROM users WHERE username = ?", (username,))
            row = cur.fetchone()
            if row and bcrypt.check_password_hash(row[1], password):
                login_user(User(id=row[0], username=username))
                flash("✅ Login successful!", "success")
                return redirect(url_for("dashboard"))
        flash("❌ Invalid credentials", "danger")
    return render_template("login.html")

@app.route('/login/microsoft')
def login_microsoft():
    redirect_uri = 'http://localhost:5000/authorize/microsoft'
    return oauth.microsoft.authorize_redirect(redirect_uri)

@app.route('/authorize/microsoft')
def authorize_microsoft():
    token = oauth.microsoft.authorize_access_token()
    user_info = oauth.microsoft.parse_id_token(token)

    # Login or register user logic here
    username = user_info['preferred_username']

    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        if row:
            user_id = row[0]
        else:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, '')", (username,))
            user_id = cursor.lastrowid
            conn.commit()

    login_user(User(id=user_id, username=username))
    return redirect('/dashboard')

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    prefix = f"{current_user.username}/"
    blob_list = container_client.list_blobs(name_starts_with=prefix)
    files = [{
        "filename": blob.name.split("/")[-1],
        "url": f"https://{AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net/{AZURE_CONTAINER_NAME}/{blob.name}"
    } for blob in blob_list]
    return render_template("dashboard.html", username=current_user.username, files=files)

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files.get('file')
    if not file or file.filename == '':
        flash("❌ No file selected", "danger")
        return redirect(url_for("dashboard"))

    filename = secure_filename(file.filename)
    local_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(local_path)

    blob_path = f"{current_user.username}/{filename}"
    blob_client = blob_service_client.get_blob_client(AZURE_CONTAINER_NAME, blob_path)
    with open(local_path, "rb") as data:
        blob_client.upload_blob(data, overwrite=True)

    with sqlite3.connect("users.db") as conn:
        conn.execute(
            "INSERT INTO user_files (user_id, filename, filepath, uploaded_at) VALUES (?, ?, ?, ?)",
            (current_user.id, filename, local_path, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
    flash("✅ File uploaded successfully!", "success")
    return redirect(url_for("dashboard"))

@app.route("/download/<filename>")
@login_required
def download(filename):
    blob_path = f"{current_user.username}/{filename}"
    sas_token = generate_blob_sas(
        account_name=AZURE_STORAGE_ACCOUNT_NAME,
        container_name=AZURE_CONTAINER_NAME,
        blob_name=blob_path,
        account_key=AZURE_STORAGE_ACCOUNT_KEY,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(minutes=10)
    )
    return jsonify({
        "file_url": f"https://{AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net/{AZURE_CONTAINER_NAME}/{blob_path}?{sas_token}"
    })

@app.route("/delete/<filename>", methods=["DELETE"])
@login_required
def delete_file(filename):
    blob_path = f"{current_user.username}/{filename}"
    try:
        blob_service_client.get_blob_client(AZURE_CONTAINER_NAME, blob_path).delete_blob()
        with sqlite3.connect("users.db") as conn:
            conn.execute("DELETE FROM user_files WHERE user_id = ? AND filename = ?", (current_user.id, filename))
        return jsonify({"message": "✅ File deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Share: Generate and store a short UUID as a key for later lookup
@app.route("/generate_share_link/<filename>")
@login_required
def generate_share_link(filename):
    share_id = str(uuid.uuid4())[:8]
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE user_files SET share_link = ? WHERE user_id = ? AND filename = ?",
                (share_id, current_user.id, filename)
            )
            if cursor.rowcount == 0:
                return jsonify({"error": "File not found"}), 404

        return jsonify({
            "share_url": url_for("access_shared_file", share_id=share_id, _external=True)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Share: Serve the shared file from Azure with a temporary SAS URL
@app.route("/access_shared_file/<share_id>")
def access_shared_file(share_id):
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT filename, user_id FROM user_files WHERE share_link = ?", (share_id,))
        row = cursor.fetchone()

    if not row:
        return jsonify({"error": "Invalid or expired share link"}), 404

    filename, user_id = row
    # Get username of the owner to form blob path
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
        user_row = cursor.fetchone()
    if not user_row:
        return jsonify({"error": "User not found"}), 404

    username = user_row[0]
    blob_path = f"{username}/{filename}"

    try:
        sas_token = generate_blob_sas(
            account_name=AZURE_STORAGE_ACCOUNT_NAME,
            container_name=AZURE_CONTAINER_NAME,
            blob_name=blob_path,
            account_key=AZURE_STORAGE_ACCOUNT_KEY,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(minutes=30)
        )

        sas_url = f"https://{AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net/{AZURE_CONTAINER_NAME}/{blob_path}?{sas_token}"
        return redirect(sas_url)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------- DB Initialization ----------
def init_db():
    with sqlite3.connect("users.db") as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                filepath TEXT NOT NULL,
                uploaded_at TEXT,
                share_link TEXT
            )
        ''')

# ---------- Run App ----------
if __name__ == "__main__":
    init_db()
    app.run(host="localhost", port=5000, debug=True)  # Updated to specify host and port
