from models.user import db
import datetime
import json

class Analysis(db.Model):
    __tablename__ = 'analysis'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    image_path = db.Column(db.String(200), nullable=False)
    result_data = db.Column(db.Text, nullable=False)  # JSON-serialized data
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    @property
    def skin_type(self):
        data = json.loads(self.result_data)
        return data.get('skin_type', 'Unknown')
    
    @property
    def date(self):
        return self.created_at
    
    def __repr__(self):
        return f'<Analysis {self.id} for User {self.user_id}>' 