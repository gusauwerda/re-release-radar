#!/usr/bin/python3

import spotipy
import os
from spotipy.oauth2 import SpotifyOAuth
from flask import Flask, url_for, session, request, redirect
import time
from flask import (
    Flask,
)
from dotenv import load_dotenv

from flask_session import Session
import boto3
from boto3.dynamodb.types import TypeDeserializer

from src.database.dynamo import DynamoDB

load_dotenv()

app = Flask(__name__)

app.secret_key = "super secret key"
app.config["SESSION_TYPE"] = "filesystem"

app.config["SESSION_COOKIE_NAME"] = "spotify-login-session"
app.config["SESSION_FILE_DIR"] = "/tmp"
app.config["SESSION_TYPE"] = "filesystem"

Session(app)

GENERATED_PLAYLIST_NAME = "Re-released Radar"
GENERATED_PLAYLIST_DESCRIPTION = "Re-release my radar with unknown music this time."
IDS = []
track_ids = []


dynamodb = DynamoDB(boto3.client("dynamodb"))

USERS_TABLE = os.environ["USERS_TABLE"]

@app.route("/")
def login():
    client_id = os.environ.get("SPOTIPY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIPY_CLIENT_SECRET")

    if client_id and client_secret:
        sp_oauth = create_spotify_oauth(
            client_id=client_id, client_secret=client_secret
        )
    else:
        return "Error: client_id and client_secret required"

    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)


@app.route("/authorize")
def authorize():
    sp_oauth = create_spotify_oauth()

    if session.get("token_info"):
        session.pop("token_info")

    code = request.args.get("code")

    token_info = sp_oauth.get_access_token(code, check_cache=False)

    session["token_info"] = token_info
    sp = get_sp()

    dynamodb.update(sp.current_user()["display_name"], token_info)

    return redirect("/{}/update-playlist".format(os.environ.get("STAGE")))


@app.route("/seed-genres")
def seed_genres():
    sp = get_sp()
    return sp.recommendation_genre_seeds()


@app.route("/update-playlist".format(os.environ.get("STAGE")))
def create_re_release_radar_playlist(sp=None):

    if sp == None:
        sp = get_sp()

    playlist_id = get_or_create_playlist(
        sp, GENERATED_PLAYLIST_NAME, GENERATED_PLAYLIST_DESCRIPTION
    )
    seed_tracks = get_seed_tracks(sp, 5)

    recommendations = sp.recommendations(seed_tracks=seed_tracks, limit=20)
    track_ids = []

    for track in recommendations["tracks"]:
        track_ids.append(track["id"])

    print("Updating playlist for {}".format(sp.current_user()["display_name"]))
    update_playlist(sp, playlist_id=playlist_id, track_ids=track_ids)

    return "Completed playlist update for {}".format(sp.current_user()["display_name"])


def create_new_album_release_playlist(sp=None):
    if sp == None:
        sp = get_sp()

    track_ids = []

    for album_item in sp.new_releases()["albums"]["items"]:
        album_data = sp.album(album_item["id"])

        for track in album_data["tracks"]["items"]:
            track_ids.append(track["id"])

    playlist_id = get_or_create_playlist(sp, "New album releases", "New album releases")
    update_playlist(sp, playlist_id=playlist_id, track_ids=track_ids[:99])
    print("Updated album playlist with 99 new tracks")


def update_playlist(sp, playlist_id, track_ids):
    if sp == None:
        sp = get_sp()
    sp.playlist_replace_items(playlist_id=playlist_id, items=track_ids)


def get_seed_tracks(sp, number_of_tracks):
    track_ids = []

    if sp == None:
        sp = get_sp()
    tracks = sp.current_user_saved_tracks(limit=number_of_tracks)
    for track in tracks["items"]:
        track_ids.append(track["track"]["id"])
    return track_ids


def get_all_liked_songs(page=0):
    limit = 50
    offset = limit * page

    sp = get_sp()
    tracks = sp.current_user_saved_tracks(limit=limit, offset=offset)["items"]

    spotify_ids = [item["track"]["id"] for item in tracks]

    if len(spotify_ids) == 50:
        IDS.append(spotify_ids)
        get_all_liked_songs(page + 1)
    else:
        IDS.append(spotify_ids)

    return spotify_ids, tracks


def get_or_create_playlist(sp, playlist_name, playlist_description):
    if sp == None:
        sp = get_sp()

    playlists = sp.current_user_playlists()

    for playlist in playlists["items"]:
        if playlist["name"] == playlist_name:
            return playlist["id"]

    playlist = sp.user_playlist_create(
        sp.current_user()["id"],
        playlist_name,
        public=True,
        collaborative=False,
        description=playlist_description,
    )

    return playlist["id"]


@app.route("/view-db")
def test_db_items():
    paginator = dynamodb.dynamodb_client.get_paginator("scan")
    response_iterator = paginator.paginate(TableName=USERS_TABLE)
    for page in response_iterator:
        
        for item in page["Items"]:
            deserializer = TypeDeserializer()
            user_data = {k: deserializer.deserialize(v) for k, v in item.items()}
            print("User data: " + str(user_data))
            print(" ------- ")


def get_sp():
    session["token_info"], authorized = get_token()
    if not authorized:
        return redirect("/")
    sp = spotipy.Spotify(auth=session.get("token_info").get("access_token"))
    return sp


def auto_refresh_albums(event, context):

    with app.app_context():
        paginator = dynamodb.dynamodb_client.get_paginator("scan")

        response_iterator = paginator.paginate(TableName=USERS_TABLE)

        for page in response_iterator:
            for item in page["Items"]:

                deserializer = TypeDeserializer()
                user_data = {k: deserializer.deserialize(v) for k, v in item.items()}

                print(
                    "Refreshing new album releases for {}".format(
                        user_data.get("userId")
                    )
                )

                token_info = eval(user_data.get("token_info"))

                is_token_expired = token_info.get("expires_in") - int(time.time()) < 60
                if is_token_expired:
                    sp_oauth = create_spotify_oauth()
                    token_info = sp_oauth.refresh_access_token(
                        token_info.get("refresh_token")
                    )
                    user = sp.current_user()["display_name"]
                    print("Refreshed token_info for {}", user)
                    dynamodb.update(user, token_info)

                sp = spotipy.Spotify(auth=token_info.get("access_token"))

                create_new_album_release_playlist(sp)
        print("Auto refresh complete.")


def auto_refresh_playlist(event, context):

    with app.app_context():

        paginator = dynamodb.dynamodb_client.get_paginator("scan")
        response_iterator = paginator.paginate(TableName=USERS_TABLE)

        for page in response_iterator:
            for item in page["Items"]:

                deserializer = TypeDeserializer()
                user_data = {k: deserializer.deserialize(v) for k, v in item.items()}
                token_info = eval(user_data.get("token_info"))

                is_token_expired = token_info.get("expires_in") - int(time.time()) < 60
                if is_token_expired:
                    sp_oauth = create_spotify_oauth()
                    token_info = sp_oauth.refresh_access_token(
                        token_info.get("refresh_token")
                    )

                sp = spotipy.Spotify(auth=token_info.get("access_token"))
                if is_token_expired:
                    update_db(sp.current_user()["display_name"], token_info)

                create_re_release_radar_playlist(sp)
        print("Auto refresh complete.")


def get_token():
    token_valid = False
    token_info = session.get("token_info", {})

    if not (session.get("token_info", False)):
        token_valid = False
        return token_info, token_valid

    now = int(time.time())
    is_token_expired = session.get("token_info").get("expires_at") - now < 60

    if is_token_expired:
        sp_oauth = create_spotify_oauth()
        token_info = sp_oauth.refresh_access_token(
            session.get("token_info").get("refresh_token")
        )

    token_valid = True
    return token_info, token_valid


def create_spotify_oauth(
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
):
    app.config["PREFERRED_URL_SCHEME"] = "https"
    app.config["SERVER_NAME"] = os.environ.get("SERVER")
    redirect_uri = 'https://{}/{}/authorize'.format(os.environ.get("SERVER"), os.environ.get("STAGE"))

    with app.app_context():
        return SpotifyOAuth(
            scope="playlist-modify-public,playlist-modify-private,user-library-read",
            redirect_uri=redirect_uri,
            client_id=client_id,
            client_secret=client_secret,
            cache_path="/tmp/.cache",
        )


if __name__ == "__main__":
    app.run()
