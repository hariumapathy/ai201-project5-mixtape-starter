## Codebase Map
The data tables/objects are defined in models.py. The important data scheme to note are:
- User
- Tag
- Song
- ListeningEvent
- Rating
- Playlist
- Notification

There are various relational tables that maintain pairings between these objects, such as songs and tags, playlists and songs, etc.

The logic is separated into the services/*_service.py files, and the routing is handled in the routes/ files.

Routes:
- feed.py
    - to get friends listening now, activity
- playlists.py
    - any endpoints related to creating and updating playlists
- songs.py
    - Search songs and their info, rate songs, and record listening events
- users.py
    - Search a user, get listening streak, see notifications, and mark notifications as read

Services:
- feed_service.py
    - handles getting friends listening now, and their recent listening events
- notification_service.py
    - create, get, read notifications; add to playlist and rate songs, and notify for both actions
- playlist_service.py
    - create a playlist, fetch a playlist, get songs in a playlist, get playlists made by a given user
- search_service.py
    - search for songs by title/artist, or search by song ID
- streak_service.py
    - record a listening event & update listening streak; fetch listening streak for a given user

Data Flow - Feature: Get all the songs for a given playlist
1. POST /playlists/<playlist_id>/songs
2. POST request handled in routes/playlists.py
3. function get_playlist_songs() is called in services/playlist_service.py
4. A list of Song dictionaries is returned if playlist_id is found, else ValueError is raised

Patterns:
- Separation of route handling and logic via services
- Lots of relational tables to connect songs, playlists, users, tags, listening events, etc.
- Heavy use of uniquely generated IDs as primary keys, rather than composite primary keys of multiple fields (ex: songs IDs, playlist IDs, user IDs, etc)


## Root Cause Analysis

### 1 - My listening streak keeps resetting 

**Issue Number, Title:**
1, My listening streak keeps resetting 


**Reproducing the Bug:**
1. Get the user ID for the username "Nova", who initially has a listening streak of 7 (id: bb9c01bc-55e6-4802-9081-fc5c98231224)
2. GET localhost:5000/users/bb9c01bc-55e6-4802-9081-fc5c98231224; response is below:
```
{
    "id": "bb9c01bc-55e6-4802-9081-fc5c98231224",
    "last_listened_at": "2026-07-07T01:18:06.978503",
    "listening_streak": 7,
    "username": "nova"
}
```
3. Copy and paste reproduce_bug_1.py in a flask shell: Calls update_listening_streak() with a Sunday datetime, to trigger the bug, and prints the user's streak before and after; terminal input and output is below:
```
$ FLASK_APP=app:create_app flask shell
Ctrl click to launch VS Code Native REPL
Python 3.11.15 | packaged by Anaconda, Inc. | (main, Jun 11 2026, 15:12:53) [MSC v.1942 64 bit (AMD64)] on win32
App: app
Instance: C:\Users\hariu\Documents\Summer2026CodePathCourses\AI201\Project_5_MixtapeBugHunt\ai201-project5-mixtape-starter\instance
>>> # still in flask shell
>>> from services.streak_service import update_listening_streak
>>> from models import User
>>> from datetime import datetime, timezone, timedelta
>>> from app import db
>>> 
>>> u = User.query.filter_by(username="nova").first()
>>> 
>>> print("BEFORE: ", u.listening_streak) 
BEFORE:  7
>>> 
>>> # now simulate "now" being Sunday June 28, 2026
>>> sunday = datetime(2026, 6, 28, 12, 0, tzinfo=timezone.utc)
>>> update_listening_streak(u, sunday)
>>> print("AFTER: ", u.listening_streak)  # see what happens vs. what you'd expect
AFTER:  1
>>> 
```
In the output, the listening streak resets to 1, which matches the reported bug.


**Finding the Root Cause:**
- The only way to change a user streak is to record a listening event. This is handled by the route in songs.py, specifically a POST request to  /songs/<song_id>/listen
- The service function this route calls is record_listening_event() in streak_service.py
- This function adds a Listening event to the DB, then calls update_listening_streak()
- Therefore, this function is likely where the bug resides, since the update logic is contained within it

**The Root Cause:**
In the docstring of the function, the streak rules are that the streak should be incremented for listens within a 1 day period, reset to 1 if the recent listens are more than 1 day apart, and not changed for multiple listens in the same day. 

However, there is a line in the function that contradict the docstring:
```python
    if days_since_last == 0:
        # Already updated today — no change needed
        return
    elif days_since_last == 1 and today.weekday() != 6:
        user.listening_streak += 1
    else:
        user.listening_streak = 1
```
The check `today.weekday() != 6` results in the streak resetting when `today.weekday() == 6`, which occurs on Sundays. Therefore, the streak resets to 1 for listens on Sundays, regardless of whether the user was maintaining a streak or not.

**Fix and Side-Effect Check:**
The fix is to remove the check `and today.weekday() != 6`. This prevents the unneeded Sunday reset.

To check for side-effects, I tried adding a Sunday listening event for a user with an active streak, a listening event on a weekday the next day, and a listening event more than 1 day apart (to ensure the reset logic still works). If all three of the streak cases work, then the fix was successful. 

I used the Flask shell for much of these side-effect checks. Here is one of the checks, generated with the help of Claude:
```
$ FLASK_APP=app:create_app flask shell
Ctrl click to launch VS Code Native REPL
Python 3.11.15 | packaged by Anaconda, Inc. | (main, Jun 11 2026, 15:12:53) [MSC v.1942 64 bit (AMD64)] on win32
App: app
Instance: C:\Users\hariu\Documents\Summer2026CodePathCourses\AI201\Project_5_MixtapeBugHunt\ai201-project5-mixtape-starter\instance
>>> from services.streak_service import update_listening_streak
>>> from models import User
>>> from datetime import datetime, timezone
>>> from app import db
>>> 
>>> u = User.query.filter_by(username="nova").first()
>>> 
>>> # manually set a known state: streak of 7, last listened Saturday June 27
>>> u.listening_streak = 7
>>> u.last_listened_at = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)
>>> db.session.commit()
>>> 
>>> print("BEFORE:", u.listening_streak)
BEFORE: 7
>>> 
>>> sunday = datetime(2026, 6, 28, 12, 0, tzinfo=timezone.utc)  # exactly 1 day later
>>> update_listening_streak(u, sunday)
>>> 
>>> print("AFTER:", u.listening_streak)  # expect 8, not 1
AFTER: 8
>>> 
```
Notice that on a Sunday listen, the streak does not reset.

### 2 - Friends Listening Now shows people from yesterday

**Issue Number, Title:**
2, Friends Listening Now shows people from yesterday

**Reproducing the Bug:**
1. Pick a user with friends, I chose username "Nova", id: bb9c01bc-55e6-4802-9081-fc5c98231224
2. GET localhost:5000/feed/bb9c01bc-55e6-4802-9081-fc5c98231224/listening-now; response below:
```
{
    "count": 3,
    "feed": [
        {
            "friend": {
                "id": "56e7b611-210e-4687-9a73-76319cbb7c8a",
                "last_listened_at": "2026-07-06T02:18:06.978503",
                "listening_streak": 3,
                "username": "darius"
            },
            "listened_at": "2026-07-07T02:08:06.978503",
            "song": {
                "album": null,
                "artist": "The Wanderers",
                "genre": "indie rock",
                "id": "d92b3d04-a952-48d1-a46f-25eafe38cf1c",
                "share_note": null,
                "shared_at": "2026-07-02T02:18:06.978503",
                "shared_by": "bb9c01bc-55e6-4802-9081-fc5c98231224",
                "tags": [],
                "title": "Midnight Drive"
            }
        },
        {
            "friend": {
                "id": "c819dedc-1f90-4e7d-ae94-f62c1c0af720",
                "last_listened_at": null,
                "listening_streak": 0,
                "username": "simone"
            },
            "listened_at": "2026-07-07T02:03:06.978503",
            "song": {
                "album": null,
                "artist": "Elara Moon",
                "genre": "ambient",
                "id": "8c27f7ea-4fc1-4c12-b3a1-f8a45c59f99a",
                "share_note": null,
                "shared_at": "2026-07-02T02:18:06.978503",
                "shared_by": "bb9c01bc-55e6-4802-9081-fc5c98231224",
                "tags": [],
                "title": "Still Waters"
            }
        },
        {
            "friend": {
                "id": "925abee5-78d7-419e-894f-b2c06f4b2f16",
                "last_listened_at": "2026-07-06T23:18:06.978503",
                "listening_streak": 12,
                "username": "kenji"
            },
            "listened_at": "2026-07-07T01:58:06.978503",
            "song": {
                "album": null,
                "artist": "Coastal Highway",
                "genre": "indie",
                "id": "a1d3618e-4709-4464-a8da-1a666e74423d",
                "share_note": null,
                "shared_at": "2026-07-02T02:18:06.978503",
                "shared_by": "bb9c01bc-55e6-4802-9081-fc5c98231224",
                "tags": [],
                "title": "First Light"
            }
        }
    ]
}
```
Given that the UTC time during this request was July 7, 2026, 4:12, some of the entries are from previous days, which is older than the 24 hour threshold set in feed_service.py. This matches the reported bug that people from yesterday are being shown in Friends Listening Now.

**Finding the Root Cause:**
- To see friends listening now, that is handled in routes/feed.py, with GET feed/<user_id>/listening-now calling get_friends_listening_now() as the main service logic
- get_friends_listening_now() lives in service/feed_service.py
- The bug is likely in the querying and filtering applied in the get_friends_listening_now() function
- The docstring says that the function returns a list of friends and their recent songs, where "recent" is defined as being within a 24 hour threshold at the top of feed_service.py
- However, after looking through seed_data.py, the comments note that:
```
# Recent events (within the past 30 minutes) — should appear in "listening now"'
...
...
# Older events (1–14 days ago) — should NOT appear in "listening now" after fix
```


**The Root Cause:**
The filtering applied incorrectly uses a 24 hour threshold cutoff. In this case, the "broken" logic is a matter of using the wrong threshold. Since `RECENT_THRESHOLD = timedelta(hours=24)`, listening events from friends in a previous day can appear. From the seed_data.py comments, we know that this is not the intention.

**Fix and Side-Effect Check:**
At the top of feed_service.py, update `RECENT_THRESHOLD` to `RECENT_THRESHOLD = timedelta(minutes=30)`.

After this fix, I reran GET localhost:5000/feed/bb9c01bc-55e6-4802-9081-fc5c98231224/listening-now in Postman. The response is below:
```
{
    "count": 0,
    "feed": []
}
```
Since none of the entries were recent (within 30 minutes), no friends are listed in this GET request.

To confirm, I reran seed_data.py, and grabbed a new user ID by running get_IDs_for_bug_reproduce.py (I chose bf5bd6c6-dea3-4269-b00e-a0d20dc5720e, which is the username "nova").

In Postman, did GET localhost:5000/feed/bf5bd6c6-dea3-4269-b00e-a0d20dc5720e/listening-now, response is below:
```
{
    "count": 3,
    "feed": [
        {
            "friend": {
                "id": "391fb218-dccb-47b2-b649-b2cce539a5f4",
                "last_listened_at": "2026-07-06T20:24:51.689701",
                "listening_streak": 3,
                "username": "darius"
            },
            "listened_at": "2026-07-07T20:14:51.689701",
            "song": {
                "album": null,
                "artist": "The Wanderers",
                "genre": "indie rock",
                "id": "1219fa09-1f88-41c0-a4b2-cba5cb51ae42",
                "share_note": null,
                "shared_at": "2026-07-02T20:24:51.689701",
                "shared_by": "bf5bd6c6-dea3-4269-b00e-a0d20dc5720e",
                "tags": [],
                "title": "Midnight Drive"
            }
        },
        {
            "friend": {
                "id": "3a490a23-3de6-40f1-9cc9-91d3283a868b",
                "last_listened_at": null,
                "listening_streak": 0,
                "username": "simone"
            },
            "listened_at": "2026-07-07T20:09:51.689701",
            "song": {
                "album": null,
                "artist": "Elara Moon",
                "genre": "ambient",
                "id": "c844a69f-fd69-4d57-90d1-b3a819a5d471",
                "share_note": null,
                "shared_at": "2026-07-02T20:24:51.689701",
                "shared_by": "bf5bd6c6-dea3-4269-b00e-a0d20dc5720e",
                "tags": [],
                "title": "Still Waters"
            }
        },
        {
            "friend": {
                "id": "bd9bea3b-92c6-4175-a320-7af4ed4c0f04",
                "last_listened_at": "2026-07-07T17:24:51.689701",
                "listening_streak": 12,
                "username": "kenji"
            },
            "listened_at": "2026-07-07T20:04:51.689701",
            "song": {
                "album": null,
                "artist": "Coastal Highway",
                "genre": "indie",
                "id": "76d27b62-753f-4e6d-8308-a400bdf4ff07",
                "share_note": null,
                "shared_at": "2026-07-02T20:24:51.689701",
                "shared_by": "bf5bd6c6-dea3-4269-b00e-a0d20dc5720e",
                "tags": [],
                "title": "First Light"
            }
        }
    ]
}
```
This request was made at UTC datetime July 7th, 20265 at 8:27 PM.

I then repeated this with multiple user IDs, ensuring that the entries fell within the 30 minute threshold.



### 4 - I got notified when a friend added my song to a playlist but not when they rated it

**Issue Number, Title:**
 4, I got notified when a friend added my song to a playlist but not when they rated it

**Reproducing the Bug:**
1. Pick a song and note its shared_by user ID. I chose the song with the name "Midnight Drive". GET localhost:5000/songs/search?q=Drive, response below:
```
{
    "count": 1,
    "results": [
        {
            "album": null,
            "artist": "The Wanderers",
            "genre": "indie rock",
            "id": "d92b3d04-a952-48d1-a46f-25eafe38cf1c",
            "share_note": null,
            "shared_at": "2026-07-02T02:18:06.978503",
            "shared_by": "bb9c01bc-55e6-4802-9081-fc5c98231224",
            "tags": [],
            "title": "Midnight Drive"
        }
    ]
}
```
2. Pick a different user ID that does NOT match the previous step's shared_by ID. I chose user ID 925abee5-78d7-419e-894f-b2c06f4b2f16, which belongs to username "kenji".
3. Before rating any songs, check the shared_by user ID notifications (our shared_by ID: bb9c01bc-55e6-4802-9081-fc5c98231224). GET localhost:5000/users/bb9c01bc-55e6-4802-9081-fc5c98231224/notifications, response below:
```
{
    "count": 1,
    "notifications": [
        {
            "body": "darius added your song 'Midnight Drive' to the playlist 'Late Night Vibes'.",
            "created_at": "2026-07-07T02:18:07.037119",
            "id": "5f78cb8f-fb1b-4525-b936-c185cc64ad62",
            "read": false,
            "type": "song_added_to_playlist",
            "user_id": "bb9c01bc-55e6-4802-9081-fc5c98231224"
        }
    ]
}
```
3. Rate the song "Midnight Drive" with kenji's user ID. The song ID is d92b3d04-a952-48d1-a46f-25eafe38cf1c. POST request, request body, and response are below:
```
POST REQUEST
POST localhost:5000/songs/d92b3d04-a952-48d1-a46f-25eafe38cf1c/rate

REQUEST BODY
{
    "user_id": "925abee5-78d7-419e-894f-b2c06f4b2f16",
    "score": 4
}

RESPONSE
{
    "id": "9f4aa6f1-44d8-4c76-9ca1-9ad343604c7c",
    "rated_at": "2026-07-07T18:57:52.418387",
    "score": 4,
    "song_id": "d92b3d04-a952-48d1-a46f-25eafe38cf1c",
    "user_id": "925abee5-78d7-419e-894f-b2c06f4b2f16"
}

```
4. Check shared_by user notifications again. GET localhost:5000/users/bb9c01bc-55e6-4802-9081-fc5c98231224/notifications, response below:
```
{
    "count": 1,
    "notifications": [
        {
            "body": "darius added your song 'Midnight Drive' to the playlist 'Late Night Vibes'.",
            "created_at": "2026-07-07T02:18:07.037119",
            "id": "5f78cb8f-fb1b-4525-b936-c185cc64ad62",
            "read": false,
            "type": "song_added_to_playlist",
            "user_id": "bb9c01bc-55e6-4802-9081-fc5c98231224"
        }
    ]
}

```
No new notification appears to inform the user that the song they shared was rated by kenji. This is the same issue as the reported bug.

**Finding the Root Cause:**
- To rate a song, the route is handled by songs.py via POST request to songs/<song_id>/rate, containing user_id and score in the request body
- This route calls the logic function rate_song() in notification_service.py
- Therefore, the bug is likely within the logic function rate_song()
- After comparing rate_song() to add_to_playlist() in notification_service.py (the latter is a working function that DOES create notifications), it seems that rate_song() does NOT call the create_notification() function at all.

**The Root Cause:**
Unlike add_to_playlist(), rate_song() never calls create_notification(), so a rating notification is never made in the first place.

**Fix and Side-Effect Check:**
The fix is to add a call to create_notification(), which should contain some descriptive message informing the user that shared the song, that another user rated the song. Following the logic of add_to_playlist(), if the user rates a song shared by themselves, then a notification should not be created.

The rate_song() function checks between a new rating, and an updated rating. Since the docstring does not specify, I decided to create a notification for BOTH new ratings and updated ratings, even if it might sound repetitive at times.

The fix was to add a few lines of code to create a notification:
```
 # Fix: create a notification, if the shared_by user ID and rater user_id are different
    if song.shared_by != user_id:
        create_notification(
            user_id=song.shared_by,
            notification_type="song_rated",
            body=f"{user_id.username} rated your song '{song.title}' as {score}/5.",
        )
```

To check for side-effects, I reran the bug reproduction steps, this time picking a new song and a new rater user_id, and then checking the notifications of the shared_by user before and after the rating call, to ensure that a new notification appeared.

I also rated a song, using the same user_id as the shared_by user, to ensure that self-notification do not occur.

I also re-rated songs, to ensure that the updated scores came in as new notifications (as per my design decision).

### 5 - The last song in a playlist never shows up

**Issue Number, Title:**
5, The last song in a playlist never shows up

**Reproducing the Bug:**
1. Pick a playlist ID. I chose 995b5c0d-585d-4127-a3a8-6c639f044274. GET localhost:5000/playlists/995b5c0d-585d-4127-a3a8-6c639f044274/songs, response below:
```
{
    "created_at": "2026-07-07T02:18:07.027717",
    "created_by": "bb9c01bc-55e6-4802-9081-fc5c98231224",
    "id": "995b5c0d-585d-4127-a3a8-6c639f044274",
    "is_collaborative": true,
    "name": "Late Night Vibes"
}
```
2. Get the list of songs in that playlist. More importantly, the count of songs is what we will use. GET localhost:5000/playlists/995b5c0d-585d-4127-a3a8-6c639f044274/songs, response below:
```
{
    "count": 6,
    "songs": [
        {
            "album": null,
            "artist": "The Wanderers",
            "genre": "indie rock",
            "id": "d92b3d04-a952-48d1-a46f-25eafe38cf1c",
            "share_note": null,
            "shared_at": "2026-07-02T02:18:06.978503",
            "shared_by": "bb9c01bc-55e6-4802-9081-fc5c98231224",
            "tags": [],
            "title": "Midnight Drive"
        },
        {
            "album": null,
            "artist": "Elara Moon",
            "genre": "ambient",
            "id": "8c27f7ea-4fc1-4c12-b3a1-f8a45c59f99a",
            "share_note": null,
            "shared_at": "2026-07-02T02:18:06.978503",
            "shared_by": "bb9c01bc-55e6-4802-9081-fc5c98231224",
            "tags": [],
            "title": "Still Waters"
        },
        {
            "album": null,
            "artist": "Coastal Highway",
            "genre": "indie",
            "id": "a1d3618e-4709-4464-a8da-1a666e74423d",
            "share_note": null,
            "shared_at": "2026-07-02T02:18:06.978503",
            "shared_by": "bb9c01bc-55e6-4802-9081-fc5c98231224",
            "tags": [],
            "title": "First Light"
        },
        {
            "album": null,
            "artist": "Street Collective",
            "genre": "hip-hop",
            "id": "510fe625-3950-430a-b3e0-4d221f80eca3",
            "share_note": null,
            "shared_at": "2026-07-04T02:18:06.978503",
            "shared_by": "56e7b611-210e-4687-9a73-76319cbb7c8a",
            "tags": [
                "hip-hop"
            ],
            "title": "Block Party"
        },
        {
            "album": null,
            "artist": "Nova Blix",
            "genre": "lo-fi",
            "id": "e103ac7b-bbc9-4be1-8712-32a8fc15c2ba",
            "share_note": null,
            "shared_at": "2026-07-04T02:18:06.978503",
            "shared_by": "56e7b611-210e-4687-9a73-76319cbb7c8a",
            "tags": [
                "lo-fi"
            ],
            "title": "Late Night Session"
        },
        {
            "album": null,
            "artist": "Solange K",
            "genre": "r&b",
            "id": "fa6669a0-3e9f-433b-a340-be4d9a561151",
            "share_note": null,
            "shared_at": "2026-07-04T02:18:06.978503",
            "shared_by": "56e7b611-210e-4687-9a73-76319cbb7c8a",
            "tags": [
                "r&b"
            ],
            "title": "Golden Hour"
        }
    ]
}
```
Notice there are 6 songs. When examining see_data.py, we can see that the playlistg "Late Night Vibes" is created with 7 songs ([s for s, _ in all_songs[:7]], [:7] is 7 items). Therefore, one song is being omitted from the final response and count. This issue matches the reported bug (where the last song does not appear in the listing).

**Finding the Root Cause:**
- To get the list of songs in a playlist, the route is in playlists.py, and is done via GET request to /<playlist_id>/songs
- This route calls get_playlist_songs() in playlist_service.py
- The bug likely has to do with the way querying or list processing was handled, since that is the bulk of the logic in the get_playlist_songs() function

**The Root Cause:**
The last line of the get_playlist() function is:
```python
return [song.to_dict() for song in songs[:-1]]
```

The indexing songs[:-1] excludes the last element in the list, which results in the count being off by one, and the final song in the playlist not appearing in the listing. This indexing contradicts the docstring, which states that the function returns *all* songs in a playlist.

**Fix and Side-Effect Check:**
The Fix: Change the last line of get_playlist_songs() to:
```python
return [song.to_dict() for song in songs]
```

For Side-Effect Checks, I did:
- Reran the bug reproduction steps with the same playlist, this time ensuring that the count was 7, instead of the incorrectly displayed 6 songs from before the fix
- Created a single-song playlist, and ensured that the listing was not empty (that is, it contained one song)
- Empty playlist still should contain a count of zero and an empty list
- Ensure that playlist song order is preserved with respect to position

