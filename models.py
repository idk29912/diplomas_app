from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid

db = SQLAlchemy()

def gen_uuid():
    return str(uuid.uuid4())

class School(db.Model):
    __tablename__ = "schools"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    cct = db.Column(db.String(50), nullable=False)
    turno = db.Column(db.String(50), nullable=True)
    director = db.Column(db.String(120), nullable=True)
    coordinador = db.Column(db.String(120), nullable=True)

class Course(db.Model):
    __tablename__ = "courses"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    nivel = db.Column(db.String(50), nullable=False)
    horas = db.Column(db.String(20), nullable=False)
    competencias = db.Column(db.Text, nullable=True)
    modulos = db.Column(db.Text, nullable=True)

class Student(db.Model):
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    curp = db.Column(db.String(18), unique=True, nullable=False)
    nombre = db.Column(db.String(200), nullable=False)
    grado = db.Column(db.String(30), nullable=True)
    grupo = db.Column(db.String(10), nullable=True)

class Diploma(db.Model):
    __tablename__ = "diplomas"
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    fecha = db.Column(db.String(20), nullable=False)         # YYYY-MM-DD
    hash = db.Column(db.String(64), nullable=False)          # sha256
    pdf_path = db.Column(db.String(300), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship("Student")
    course = db.relationship("Course")
    school = db.relationship("School")
