from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Email(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(120))
    subject = db.Column(db.String(200))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    has_pdf = db.Column(db.Boolean, default=False)
    pdf_emails = db.Column(db.Text)  # Store as comma-separated string
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True)
    company = db.relationship('Company', backref=db.backref('company_emails', lazy=True))

class CompanyEmail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    emails = db.relationship('CompanyEmail', backref='company', lazy=True, cascade='all, delete-orphan')
