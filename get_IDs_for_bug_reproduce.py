from app import create_app, db
from models import User, Song, Playlist

app = create_app()
with app.app_context():
    print("-- USERS --")
    for u in User.query.all():
        print(f"{u.username}: {u.id}")

    print("-- SONGS --")
    for u in Song.query.all():
        print(f"{u.title}: {u.id}: {u.artist}")

    print("-- PLAYLISTS --")
    for u in Playlist.query.all():
        print(f"{u.id}")