from app import app, db
from models.user import User

# Create database tables
with app.app_context():
    # Recreate all tables
    db.drop_all()
    db.create_all()
    
    # Create a test user
    test_user = User(
        username='testuser',
        email='test@example.com',
        first_name='Test',
        last_name='User'
    )
    test_user.set_password('password123')
    
    # Add test user to database
    db.session.add(test_user)
    db.session.commit()
    
    print("Database initialized with test user:")
    print("Username: testuser")
    print("Email: test@example.com")
    print("Password: password123") 