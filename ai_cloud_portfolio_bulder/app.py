from flask import Flask, render_template, request, redirect, url_for, session, make_response
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super_secret_dev_key")

# -----------------------------
# UPLOAD FOLDER
# -----------------------------

UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# -----------------------------
# MONGODB CONNECTION
# -----------------------------

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise ValueError("No MONGO_URI found in environment variables.")

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    # Trigger a call to verify connection
    client.admin.command('ping')
    db = client["ai_portfolio_db"]
    users_collection = db["users"]
    portfolio_collection = db["portfolios"]
except Exception as e:
    print(f"CRITICAL: Could not connect to MongoDB. Error: {e}")
    # In a real app, you might want to handle this more gracefully
    # but for now, we'll let it raise so the log shows it.
    raise

# -----------------------------
# AI SCORING ENGINE
# -----------------------------

def calculate_ai_score(data):
    """Analyse portfolio data and return score (0-100), breakdown, and suggestions."""
    score = 0
    breakdown = {}
    suggestions = []

    # ── 1. Profile (15 pts) ──────────────────────────────
    profile_pts = 0
    if data.get("name", "").strip():  profile_pts += 4
    if data.get("role", "").strip():  profile_pts += 4
    if data.get("photo", "").strip(): profile_pts += 4
    if data.get("resume", "").strip(): profile_pts += 3
    breakdown["Profile"] = {"score": profile_pts, "max": 15}
    if not data.get("photo", "").strip():
        suggestions.append("Add a professional profile photo to make a strong first impression.")
    if not data.get("resume", "").strip():
        suggestions.append("Upload your CV / Resume so recruiters can download it directly.")
    score += profile_pts

    # ── 2. Introduction (15 pts) ─────────────────────────
    intro = data.get("intro", "").strip()
    word_count = len(intro.split()) if intro else 0
    if word_count >= 40:   intro_pts = 15
    elif word_count >= 20: intro_pts = 10
    elif word_count >= 5:  intro_pts = 5
    else:                  intro_pts = 0
    breakdown["Introduction"] = {"score": intro_pts, "max": 15}
    if word_count < 40:
        suggestions.append(f"Expand your introduction — aim for at least 40 words (currently {word_count}).")
    score += intro_pts

    # ── 3. Skills (25 pts) ───────────────────────────────
    raw_skills = data.get("skills", "")
    skills = [s.strip() for s in raw_skills.split(",") if s.strip()] if raw_skills else []
    skill_count = len(skills)
    if skill_count >= 7:   skills_pts = 25
    elif skill_count >= 5: skills_pts = 20
    elif skill_count >= 3: skills_pts = 15
    elif skill_count >= 1: skills_pts = 8
    else:                  skills_pts = 0
    breakdown["Skills"] = {"score": skills_pts, "max": 25}
    if skill_count < 5:
        suggestions.append(f"Add more technical skills — aim for at least 5 (currently {skill_count}).")
    score += skills_pts

    # ── 4. Projects (25 pts) ─────────────────────────────
    projects = [p for p in data.get("projects", []) if str(p).strip()]
    proj_count = len(projects)
    if proj_count >= 3:   proj_pts = 25
    elif proj_count == 2: proj_pts = 18
    elif proj_count == 1: proj_pts = 10
    else:                 proj_pts = 0
    breakdown["Projects"] = {"score": proj_pts, "max": 25}
    if proj_count < 3:
        suggestions.append(f"Add more projects — aim for at least 3 (currently {proj_count}).")
    score += proj_pts

    # ── 5. Certifications (10 pts) ───────────────────────
    certs = [c for c in data.get("certifications", []) if c.get("image", "").strip()]
    cert_count = len(certs)
    if cert_count >= 3:   cert_pts = 10
    elif cert_count == 2: cert_pts = 7
    elif cert_count == 1: cert_pts = 4
    else:                 cert_pts = 0
    breakdown["Certifications"] = {"score": cert_pts, "max": 10}
    if cert_count == 0:
        suggestions.append("Add certification images to validate your expertise and boost credibility.")
    score += cert_pts

    # ── 6. Professional Links (10 pts) ───────────────────
    links_pts = 0
    if data.get("linkedin", "").strip(): links_pts += 5
    else: suggestions.append("Include your LinkedIn profile link to increase professional visibility.")
    if data.get("github", "").strip():  links_pts += 5
    else: suggestions.append("Include your GitHub link to showcase your code and open-source work.")
    breakdown["Links"] = {"score": links_pts, "max": 10}
    score += links_pts

    # ── Label ────────────────────────────────────────────
    if score >= 90:   label, color = "Excellent",   "#16a34a"
    elif score >= 80: label, color = "Strong",      "#2563eb"
    elif score >= 60: label, color = "Good",        "#7c3aed"
    elif score >= 40: label, color = "Fair",        "#d97706"
    else:             label, color = "Needs Work",  "#dc2626"

    return {
        "score":       score,
        "label":       label,
        "color":       color,
        "breakdown":   breakdown,
        "suggestions": suggestions,
    }

# -----------------------------
# HOME
# -----------------------------

@app.route("/")
def home():
    return redirect(url_for("login"))

# -----------------------------
# LOGIN
# -----------------------------

@app.route("/login", methods=["GET","POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        user = users_collection.find_one({"email": email})

        if not user:
            return render_template("login.html", message="New user! Please register first.")

        if not check_password_hash(user["password"], password):
            return render_template("login.html", message="Invalid password.")

        session["user"] = email
        return redirect(url_for("dashboard"))

    return render_template("login.html")

# -----------------------------
# REGISTER
# -----------------------------

@app.route("/register", methods=["GET","POST"])
def register():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]
        confirm = request.form["confirm"]

        if users_collection.find_one({"email": email}):
            return render_template("register.html", message="User already exists.")

        if password != confirm:
            return render_template("register.html", message="Passwords do not match.")

        hashed_password = generate_password_hash(password)

        users_collection.insert_one({
            "email": email,
            "password": hashed_password
        })

        return redirect(url_for("login"))

    return render_template("register.html")

# -----------------------------
# LOGOUT
# -----------------------------

@app.route("/logout")
def logout():

    session.pop("user", None)

    return redirect(url_for("login"))

# -----------------------------
# DASHBOARD
# -----------------------------

@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect(url_for("login"))

    return render_template("dashboard.html")

# -----------------------------
# CREATE PORTFOLIO
# -----------------------------

@app.route("/create", methods=["GET","POST"])
def create_portfolio():

    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        name = request.form.get("name", "")
        role = request.form.get("role", "")
        intro = request.form.get("intro", "")
        education = request.form.get("education", "")
        skills = request.form.get("skills", "")

        project1 = request.form.get("project1", "")
        project2 = request.form.get("project2", "")
        project3 = request.form.get("project3", "")

        # Fetch existing portfolio to preserve files if not re-uploaded
        existing = portfolio_collection.find_one({"user_email": session["user"]})

        def get_filename(f, old_fname):
            if f and f.filename != "":
                fname = secure_filename(f.filename)
                f.save(os.path.join(app.config["UPLOAD_FOLDER"], fname))
                return fname
            return old_fname

        # Icons and files
        photo_file     = request.files.get("photo")
        resume_file    = request.files.get("resume")
        cert1_file     = request.files.get("cert_img1")
        cert2_file     = request.files.get("cert_img2")
        cert3_file     = request.files.get("cert_img3")

        # Contact fields
        email    = request.form.get("contact", "")
        phone    = request.form.get("phone", "")
        linkedin = request.form.get("linkedin", "")
        github   = request.form.get("github", "")

        # Get existing filenames/certs for preservation
        old_photo = existing.get("photo", "") if existing else ""
        old_resume = existing.get("resume", "") if existing else ""
        
        # Certifications are stored as a list of dicts
        old_certs = existing.get("certifications", []) if existing else []
        old_c1 = old_certs[0].get("image", "") if len(old_certs) > 0 else ""
        old_c2 = old_certs[1].get("image", "") if len(old_certs) > 1 else ""
        old_c3 = old_certs[2].get("image", "") if len(old_certs) > 2 else ""

        filename        = get_filename(photo_file, old_photo)
        resume_filename = get_filename(resume_file, old_resume)
        cert_img1_name  = get_filename(cert1_file, old_c1)
        cert_img2_name  = get_filename(cert2_file, old_c2)
        cert_img3_name  = get_filename(cert3_file, old_c3)

        # Auto intro generate
        if intro.strip() == "":
            intro = f"I am {name}, an aspiring {role} who enjoys building applications and learning new technologies to create innovative digital solutions."

        data = {

            "user_email": session["user"],
            "name": name,
            "role": role,
            "intro": intro,
            "education": education,
            "skills": skills,
            "template": request.form.get("template", "standard"),
            "projects":[
                project1,
                project2,
                project3
            ],
            "certifications":[
                {"image": cert_img1_name},
                {"image": cert_img2_name},
                {"image": cert_img3_name}
            ],
            "resume": resume_filename,
            "email": email,
            "phone": phone,
            "linkedin": linkedin,
            "github": github,
            "photo": filename,
        }

        portfolio_collection.update_one(
            {"user_email": session["user"]},
            {"$set": data},
            upsert=True
        )

        return render_template("view.html", data=data, ai=calculate_ai_score(data), is_owner=True)

    return render_template("portfolio.html")

# -----------------------------
# OWNER'S PRIVATE PORTFOLIO VIEW
# -----------------------------

@app.route("/my-portfolio")
def my_portfolio():
    if "user" not in session:
        return redirect(url_for("login"))

    portfolio = portfolio_collection.find_one({"user_email": session["user"]})

    if not portfolio:
        return render_template("not_found.html")

    # Always show AI score to the logged-in owner
    return render_template("view.html", data=portfolio, ai=calculate_ai_score(portfolio), is_owner=True)

# -----------------------------
# PUBLIC PORTFOLIO
# -----------------------------

@app.route("/portfolio/<email>")
def public_portfolio(email):

    portfolio = portfolio_collection.find_one({"user_email": email})

    if not portfolio:
        return render_template("not_found.html")

    # This is the public shareable link — AI score is never shown here
    return render_template("view.html", data=portfolio, ai=calculate_ai_score(portfolio), is_owner=False)

# -----------------------------
# DOWNLOAD PORTFOLIO
# -----------------------------

@app.route("/download_portfolio/<user_email>")
def download_portfolio(user_email):
    portfolio = portfolio_collection.find_one({"user_email": user_email})
    if not portfolio:
        return render_template("not_found.html"), 404

    # ── Inline CSS so the file is self-contained ──────────────
    css_dir = os.path.join(app.root_path, "static", "css")
    theme   = portfolio.get("template", "standard")

    def read_css(filename):
        path = os.path.join(css_dir, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    portfolio_css = read_css("portfolio.css")
    theme_css     = read_css(f"theme-{theme}.css")

    html_content = render_template(
        "view.html",
        data=portfolio,
        ai=calculate_ai_score(portfolio),
        is_owner=False,
        inline_css=True,
        portfolio_css=portfolio_css,
        theme_css=theme_css,
    )

    # ── Convert remaining /static/ paths to absolute URLs ─────
    # (covers uploaded images, devicon CDN already uses full URLs)
    base = request.host_url.rstrip("/")
    html_content = html_content.replace('src="/static/', f'src="{base}/static/')
    html_content = html_content.replace('href="/static/', f'href="{base}/static/')

    response = make_response(html_content)
    safe_name = user_email.split("@")[0].replace(".", "_")
    response.headers["Content-Disposition"] = f"attachment; filename={safe_name}_portfolio.html"
    response.headers["Content-Type"] = "text/html"
    return response

# -----------------------------
# ERROR HANDLERS
# -----------------------------

@app.errorhandler(404)
def page_not_found(e):
    return render_template("not_found.html"), 404

@app.errorhandler(500)
def server_error(e):
    return "<h1>500 Internal Server Error</h1><p>Something went wrong on our end. Please try again later.</p>", 500

# -----------------------------
# RUN
# -----------------------------

if __name__ == "__main__":
    # In production, debug should be False. We use an env var to control it.
    app.run(debug=os.getenv("DEBUG", "False") == "True")
