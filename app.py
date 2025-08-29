import os, io, csv, hashlib
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, send_file, abort, flash
from flask_sqlalchemy import SQLAlchemy
from models import db, Student, Course, School, Diploma
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
import qrcode
from PIL import Image
from urllib.parse import urlparse, urlunparse  # para limpiar UTM

load_dotenv()
BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")
SECRET_KEY = os.getenv("SECRET_KEY", "dev")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///diplomas.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

# --- LIMPIA cualquier ?utm_* de las URLs ---
@app.before_request
def strip_utm_params():
    if any(k.startswith("utm_") for k in request.args.keys()):
        parts = list(urlparse(request.url))
        parts[4] = ""  # query sin parámetros
        clean = urlunparse(parts)
        return redirect(clean, code=302)

GEN_DIR = os.path.join(os.path.dirname(__file__), "generated")
os.makedirs(GEN_DIR, exist_ok=True)

def make_qr(url):
    qr = qrcode.QRCode(box_size=5, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image()
    return img

def calc_hash(student, course, school, fecha):
    base = "|".join([
        student.curp, student.nombre, (school.nombre or ""), (school.cct or ""),
        course.nombre, (course.nivel or ""), (course.horas or ""), (fecha or "")
    ])
    return hashlib.sha256(base.encode()).hexdigest()

def draw_pdf(buf, diploma):
    from reportlab.lib.utils import ImageReader
    from reportlab.lib.colors import HexColor
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    c.setFillColor(HexColor("#FFFFFF")); c.rect(0,0,W,H, fill=1, stroke=0)
    c.setStrokeColor(HexColor("#0C4A6E")); c.setLineWidth(6); c.rect(20, 20, W-40, H-40)

    logo_path = os.path.join("static", "logos", "logo.png")
    if os.path.exists(logo_path):
        c.drawImage(logo_path, 60, H-160, width=120, height=120, mask='auto')

    c.setFont("Helvetica-Bold", 22); c.setFillColor(HexColor("#763DBC"))
    c.drawString(200, H-80, diploma.school.nombre)
    c.setFont("Helvetica", 12)
    c.drawString(200, H-100, f"CCT: {diploma.school.cct}")

    c.setFont("Helvetica-Bold", 34); c.setFillColor(HexColor("#111111"))
    c.drawCentredString(W/2, H-200, "DIPLOMA DE COMPUTACIÓN")

    st, co, sc = diploma.student, diploma.course, diploma.school
    c.setFont("Helvetica", 14)
    y = H-250
    c.drawCentredString(W/2, y, "Se otorga a")
    c.setFont("Helvetica-Bold", 20); c.drawCentredString(W/2, y-30, st.nombre)
    c.setFont("Helvetica", 14)
    c.drawCentredString(W/2, y-60, f"por haber acreditado '{co.nombre}' (Nivel {co.nivel}) con {co.horas} horas.")
    comps = (co.competencias or "")
    if len(comps) > 120: comps = comps[:117] + "..."
    c.drawCentredString(W/2, y-85, f"Competencias: {comps}")
    c.drawCentredString(W/2, y-110, f"Fecha de acreditación: {diploma.fecha}")

    dir_path = os.path.join("static", "firmas", "director.png")
    coo_path = os.path.join("static", "firmas", "coordinador.png")
    y_f = 140
    if os.path.exists(dir_path):
        c.drawImage(dir_path, 120, y_f, width=160, height=60, mask='auto')
    if os.path.exists(coo_path):
        c.drawImage(coo_path, W-280, y_f, width=160, height=60, mask='auto')

    c.setFont("Helvetica", 10)
    c.drawCentredString(200, y_f-10, sc.director or "Director(a)")
    c.drawCentredString(W-200, y_f-10, sc.coordinador or "Coordinador(a) de Computación")

    qr_url = f"{BASE_URL}{url_for('view_cert', cert_id=diploma.id)}"
    bio = io.BytesIO()
    make_qr(qr_url).save(bio, format="PNG"); bio.seek(0)
    c.drawImage(ImageReader(bio), W-160, 60, width=100, height=100, mask='auto')
    c.setFont("Helvetica", 8); c.drawString(W-160, 50, "Verificar")

    c.showPage(); c.save()

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/lookup", methods=["GET","POST"])
def lookup():
    if request.method == "GET":
        return render_template("lookup.html")
    curp = request.form.get("curp","").strip().upper()
    stu = Student.query.filter_by(curp=curp).first()
    if not stu:
        return render_template("lookup.html", error="No encontrado. Verifica tu CURP.")
    dip = Diploma.query.filter_by(student_id=stu.id).order_by(Diploma.created_at.desc()).first()
    if not dip:
        return render_template("lookup.html", error="No hay diplomas para este alumno.")
    return redirect(url_for("view_cert", cert_id=dip.id))

@app.route("/cert/<cert_id>")
def view_cert(cert_id):
    dip = Diploma.query.get(cert_id)
    if not dip: abort(404)
    ok = (dip.hash == calc_hash(dip.student, dip.course, dip.school, dip.fecha))
    return render_template("cert.html", rec=dip, ok=ok)

@app.route("/cert/<cert_id>/download.pdf")
def download_pdf(cert_id):
    dip = Diploma.query.get(cert_id)
    if not dip: abort(404)
    if not os.path.exists(dip.pdf_path): abort(404)
    return send_file(dip.pdf_path, as_attachment=True, download_name="diploma.pdf")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    pwd = request.form.get("password","")
    if pwd == ADMIN_PASSWORD:
        session["admin"] = True
        return redirect(url_for("upload"))
    flash("Contraseña incorrecta")
    return redirect(url_for("login"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

def admin_required():
    return session.get("admin") is True

@app.route("/upload", methods=["GET","POST"])
def upload():
    if not admin_required():
        return redirect(url_for("login"))

    if request.method == "GET":
        has_school = School.query.count() > 0
        has_course = Course.query.count() > 0
        return render_template("upload.html", has_school=has_school, has_course=has_course)

    action = request.form.get("action")

    if action == "create_school":
        sc = School(
            nombre=request.form.get("nombre","").strip(),
            cct=request.form.get("cct","").strip(),
            turno=request.form.get("turno","").strip(),
            director=request.form.get("director","").strip(),
            coordinador=request.form.get("coordinador","").strip()
        )
        db.session.add(sc); db.session.commit()
        flash("Escuela guardada.")
        return redirect(url_for("upload"))

    if action == "create_course":
        co = Course(
            nombre=request.form.get("c_nombre","").strip(),
            nivel=request.form.get("c_nivel","").strip(),
            horas=request.form.get("c_horas","").strip(),
            competencias=request.form.get("c_competencias","").strip(),
            modulos=request.form.get("c_modulos","").strip()
        )
        db.session.add(co); db.session.commit()
        flash("Curso guardado.")
        return redirect(url_for("upload"))

    if action == "upload_csv":
        school_id = int(request.form.get("school_id"))
        course_id = int(request.form.get("course_id"))
        fecha = request.form.get("fecha","").strip()
        file = request.files.get("csv")
        if not (school_id and course_id and fecha and file):
            flash("Faltan datos para generar.")
            return redirect(url_for("upload"))

        sc = School.query.get(school_id); co = Course.query.get(course_id)
        if not sc or not co:
            flash("Escuela o curso no válidos.")
            return redirect(url_for("upload"))

        reader = csv.DictReader(io.StringIO(file.read().decode("utf-8")))
        gen_count = 0
        for row in reader:
            curp = row["curp"].strip().upper()
            nombre = row["nombre"].strip()
            grado  = row.get("grado","").strip()
            grupo  = row.get("grupo","").strip()

            st = Student.query.filter_by(curp=curp).first()
            if not st:
                st = Student(curp=curp, nombre=nombre, grado=grado, grupo=grupo)
                db.session.add(st); db.session.flush()

            h = calc_hash(st, co, sc, fecha)
            dip = Diploma(student_id=st.id, course_id=co.id, school_id=sc.id, fecha=fecha, hash=h, pdf_path="")
            db.session.add(dip); db.session.flush()

            buf = io.BytesIO()
            draw_pdf(buf, dip)
            pdf_path = os.path.join(GEN_DIR, f"{dip.id}.pdf")
            with open(pdf_path, "wb") as f:
                f.write(buf.getvalue())

            dip.pdf_path = pdf_path
            gen_count += 1

        db.session.commit()
        flash(f"OK: {gen_count} diplomas generados.")
        return redirect(url_for("upload"))

    flash("Acción no reconocida.")
    return redirect(url_for("upload"))

@app.cli.command("init-db")
def init_db():
    with app.app_context():
        db.create_all()
        print("BD creada.")
        if School.query.count() == 0:
            db.session.add(School(nombre="Escuela Demo", cct="00XXX0000X", turno="Matutino",
                                  director="Mtra. Ana López", coordinador="Ing. Carlos Ruiz"))
        if Course.query.count() == 0:
            db.session.add(Course(nombre="Computación Básica", nivel="Inicial", horas="30",
                                  competencias="Uso básico de PC; Paint; Guardar archivos",
                                  modulos="Intro PC; Teclado; Paint"))
        db.session.commit()
        print("Datos demo listos.")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
