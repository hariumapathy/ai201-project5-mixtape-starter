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

## Bug Reproduction

### 1 - My listening streak keeps resetting 
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


### 2 - Friends Listening Now shows people from yesterday
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

### 4 - I got notified when a friend added my song to a playlist but not when they rated it
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

### 5 - The last song in a playlist never shows up
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


## Root Cause Analysis


### 1 - My listening streak keeps resetting 

**Issue Number, Title:**


**Reproducing the Bug:**

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

### 2 - Friends Listening Now shows people from yesterday

**Issue Number, Title:**


**Reproducing the Bug:**

**Finding the Root Cause:**

**The Root Cause:**

**Fix and Side-Effect Check:**

### 4 - I got notified when a friend added my song to a playlist but not when they rated it

**Issue Number, Title:**
 

**Reproducing the Bug:**

**Finding the Root Cause:**

**The Root Cause:**

**Fix and Side-Effect Check:**

### 5 - The last song in a playlist never shows up

**Issue Number, Title:**


**Reproducing the Bug:**

**Finding the Root Cause:**

**The Root Cause:**

**Fix and Side-Effect Check:**



