#!/usr/bin/python3

import spotipy
import os
from flask import Flask, session, request, redirect
import time
from flask import (
    Flask,
)
from dotenv import load_dotenv
from flask_session import Session
import boto3
from boto3.dynamodb.types import TypeDeserializer
from src.database.dynamo import DynamoDB
from src.authentication.authentication import Authentication
from src.playlist.playlist import Playlist
from src.helpers.helpers import Helpers

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
authentication = Authentication(session)
playlist = Playlist(authentication)
helpers = Helpers(authentication)

USERS_TABLE = os.environ["USERS_TABLE"]


@app.route("/")
def login():
    client_id = os.environ.get("SPOTIPY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIPY_CLIENT_SECRET")

    if client_id and client_secret:
        sp_oauth = authentication.create_spotify_oauth(
            app, client_id=client_id, client_secret=client_secret
        )
    else:
        return "Error: client_id and client_secret required"

    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)


@app.route("/authorize")
def authorize():
    sp_oauth = authentication.create_spotify_oauth(app)

    if session.get("token_info"):
        session.pop("token_info")

    code = request.args.get("code")

    token_info = sp_oauth.get_access_token(code, check_cache=False)

    session["token_info"] = token_info
    sp = authentication.get_sp()

    dynamodb.update(sp.current_user()["display_name"], token_info)

    redirect_uri = (
        "/update-playlist"
        if os.environ.get("LOCAL_DEV")
        else "/{}/update-playlist".format(os.environ.get("STAGE"))
    )

    return redirect(redirect_uri)


@app.route("/update-playlist".format(os.environ.get("STAGE")))
def create_re_release_radar_playlist(sp=None):

    if sp == None:
        sp = authentication.get_sp()

    playlist_id = playlist.get_or_create(
        sp, GENERATED_PLAYLIST_NAME, GENERATED_PLAYLIST_DESCRIPTION
    )
    seed_tracks = helpers.get_seed_tracks(sp, 5)

    recommendations = sp.recommendations(seed_tracks=seed_tracks, limit=20)
    track_ids = []

    for track in recommendations["tracks"]:
        track_ids.append(track["id"])

    print("Updating playlist for {}".format(sp.current_user()["display_name"]))
    playlist.update(sp, playlist_id=playlist_id, track_ids=track_ids)
    playlist.set_image(sp, playlist_id)

    return "Completed playlist update for {}".format(sp.current_user()["display_name"])


def create_new_album_release_playlist(sp=None):
    if sp == None:
        sp = authentication.get_sp()

    track_ids = []

    for album_item in sp.new_releases()["albums"]["items"]:
        album_data = sp.album(album_item["id"])

        for track in album_data["tracks"]["items"]:
            track_ids.append(track["id"])

    playlist_id = playlist.get_or_create(sp, "New album releases", "New album releases")
    playlist.update(sp, playlist_id=playlist_id, track_ids=track_ids[:99])
    print("Updated album playlist with 99 new tracks")


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
                    sp_oauth = authentication.create_spotify_oauth(app)
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
                    sp_oauth = authentication.create_spotify_oauth(app)
                    token_info = sp_oauth.refresh_access_token(
                        token_info.get("refresh_token")
                    )

                sp = spotipy.Spotify(auth=token_info.get("access_token"))
                if is_token_expired:
                    dynamodb.update(sp.current_user()["display_name"], token_info)

                create_re_release_radar_playlist(sp)
        print("Auto refresh complete.")


if __name__ == "__main__":
    app.run()
