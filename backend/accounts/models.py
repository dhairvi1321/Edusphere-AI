import bcrypt
from mongoengine import Document, StringField, BooleanField, DateTimeField
from datetime import datetime


class User(Document):
    meta = {'collection': 'users'}

    username = StringField(required=True, unique=True, max_length=150)
    email = StringField(required=True, unique=True)
    first_name = StringField(default='')
    last_name = StringField(default='')
    password_hash = StringField(default='')
    is_active = BooleanField(default=True)
    google_user = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.utcnow)

    def set_password(self, raw_password):
        self.password_hash = bcrypt.hashpw(raw_password.encode(), bcrypt.gensalt()).decode()

    def check_password(self, raw_password):
        if not self.password_hash:
            return False
        return bcrypt.checkpw(raw_password.encode(), self.password_hash.encode())

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    @property
    def id_str(self):
        return str(self.id)
