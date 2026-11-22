# Price calculator
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class MandiPrice(db.Model):
    __tablename__ = 'mandi_price'
    
    id = db.Column(db.Integer, primary_key=True)
    state = db.Column(db.String(100), nullable=False)
    district = db.Column(db.String(100), nullable=False)
    mandi_name = db.Column(db.String(150), nullable=False)
    commodity = db.Column(db.String(100), nullable=False)
    variety = db.Column(db.String(100), nullable=True)
    min_price = db.Column(db.Float, nullable=False)
    max_price = db.Column(db.Float, nullable=False)
    modal_price = db.Column(db.Float, nullable=False)
    arrival_date = db.Column(db.Date, nullable=False)

    def __repr__(self):
        return f"<MandiPrice {self.mandi_name} - {self.commodity}: ₹{self.modal_price}>"