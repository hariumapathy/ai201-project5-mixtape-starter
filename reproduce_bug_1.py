# still in flask shell
from services.streak_service import update_listening_streak
from models import User
from datetime import datetime, timezone, timedelta
from app import db

u = User.query.filter_by(username="nova").first()

print("BEFORE: ", u.listening_streak) 

# now simulate "now" being Sunday June 28, 2026
sunday = datetime(2026, 6, 28, 12, 0, tzinfo=timezone.utc)
update_listening_streak(u, sunday)
print("AFTER: ", u.listening_streak)  # see what happens vs. what you'd expect