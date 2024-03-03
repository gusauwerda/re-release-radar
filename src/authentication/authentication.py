from flask import redirect, url_for
import os
import time
from spotipy import SpotifyOAuth
import spotipy


class Authentication:

    def __init__(self, session):
        self.session = session

    def get_token(self):
        token_valid = False
        token_info = self.session.get("token_info", {})

        if not (self.session.get("token_info", False)):
            token_valid = False
            return token_info, token_valid

        now = int(time.time())
        is_token_expired = self.session.get("token_info").get("expires_at") - now < 60

        if is_token_expired:
            sp_oauth = self.create_spotify_oauth()
            token_info = sp_oauth.refresh_access_token(
                self.session.get("token_info").get("refresh_token")
            )

        token_valid = True
        return token_info, token_valid

    def create_spotify_oauth(
        self,
        app,
        client_id=os.getenv("SPOTIPY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    ):  
        if os.environ.get('LOCAL_DEV'):
            return SpotifyOAuth(
                scope="playlist-modify-public,playlist-modify-private,user-library-read,ugc-image-upload",
                redirect_uri=url_for('authorize', _external=True),
                client_id=client_id,
                client_secret=client_secret,
                cache_path="/tmp/.cache",
            )

        app.config["PREFERRED_URL_SCHEME"] = "https"
        app.config["SERVER_NAME"] = os.environ.get("SERVER")
        redirect_uri = "https://{}/{}/authorize".format(
            os.environ.get("SERVER"), os.environ.get("STAGE")
        )

        with app.app_context():
            return SpotifyOAuth(
                scope="playlist-modify-public,playlist-modify-private,user-library-read,ugc-image-upload",
                redirect_uri=redirect_uri,
                client_id=client_id,
                client_secret=client_secret,
                cache_path="/tmp/.cache",
            )

    def get_sp(self):
        self.session["token_info"], authorized = self.get_token()
        if not authorized:
            return redirect("/")
        sp = spotipy.Spotify(auth=self.session.get("token_info").get("access_token"))
        return sp
