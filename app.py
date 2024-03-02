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

from flask_apscheduler import APScheduler
from flask_session import Session

load_dotenv()

app = Flask(__name__)

app.secret_key = 'super secret key'
app.config['SESSION_TYPE'] = 'filesystem'

app.config['SESSION_COOKIE_NAME'] = 'spotify-login-session'
app.config['SESSION_FILE_DIR'] = '/tmp'
app.config['SESSION_TYPE'] = 'filesystem'

Session(app)

GENERATED_PLAYLIST_NAME = 'Re-released Radar'
GENERATED_PLAYLIST_DESCRIPTION = "Re-release my radar with unknown music this time."
IDS = []
CACHED_TOKENS = []
track_ids = []


@app.route('/')
def login():
    client_id = os.environ.get('SPOTIPY_CLIENT_ID')
    client_secret = os.environ.get('SPOTIPY_CLIENT_SECRET')

    if (client_id and client_secret):
        sp_oauth = create_spotify_oauth(client_id=client_id, client_secret=client_secret)
    else:
        return "Error: client_id and client_secret required"
    
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)


@app.route('/authorize')
def authorize():
    sp_oauth = create_spotify_oauth()

    if (session.get('token_info')):
        session.pop('token_info')

    code = request.args.get('code')

    token_info = sp_oauth.get_access_token(code, check_cache=False)

    session["token_info"] = token_info

    CACHED_TOKENS.append(token_info)

    return redirect('/{}/update-playlist'.format(os.environ.get('STAGE')))


@app.route('/seed-genres')
def seed_genres():
    sp = get_sp()
    return sp.recommendation_genre_seeds()


@app.route('/update-playlist'.format(os.environ.get('STAGE')))
def create_re_radar(sp=None):

    if (sp == None):
        sp = get_sp()

    get_all_liked_songs()

    playlist_id = get_or_create_playlist()
    seed_tracks = get_seed_tracks(5)

    recommendations = sp.recommendations(seed_tracks=seed_tracks, limit=20)
    track_ids = []

    skipped = 0
    for track in recommendations['tracks']:
        if (track['id'] in IDS):
            skipped += 1
            continue
        else:
            track_ids.append(track['id'])

    update_playlist(playlist_id=playlist_id, track_ids=track_ids)

    return "Complete"


def update_playlist(playlist_id, track_ids):
    sp = get_sp()
    sp.playlist_replace_items(playlist_id=playlist_id, items=track_ids)


def get_seed_tracks(number_of_tracks):
    track_ids = []

    sp = get_sp()
    tracks = sp.current_user_saved_tracks(limit=number_of_tracks)
    for track in tracks['items']:
        track_ids.append(track['track']['id'])
    return track_ids


def get_all_liked_songs(page=0):
    limit = 50
    offset = limit * page

    sp = get_sp()
    tracks = sp.current_user_saved_tracks(limit=limit, offset=offset)["items"]

    spotify_ids = [item["track"]["id"] for item in tracks]
    
    if (len(spotify_ids) == 50):
        IDS.append(spotify_ids)
        get_all_liked_songs(page + 1)
    else:
        IDS.append(spotify_ids)

    return spotify_ids, tracks


def get_or_create_playlist():
    sp = get_sp()

    playlists = sp.current_user_playlists()

    for playlist in playlists['items']:
        if (playlist['name'] == GENERATED_PLAYLIST_NAME):
            return playlist['id']
    
    playlist = sp.user_playlist_create(
        sp.current_user()['id'], 
        GENERATED_PLAYLIST_NAME, 
        public=True, 
        collaborative=False, 
        description=GENERATED_PLAYLIST_DESCRIPTION
        )
    
    return playlist['id']
        
            
def get_sp():
    session['token_info'], authorized = get_token()
    if not authorized:
        return redirect('/')
    sp = spotipy.Spotify(auth=session.get('token_info').get('access_token'))
    return sp


def auto_refresh_playlist():
    for token in CACHED_TOKENS:
        print('Refreshing playlist for {}'.format(token))
        sp_oauth = create_spotify_oauth()
        token = sp_oauth.refresh_access_token(token)
        sp = spotipy.Spotify(auth=token)
        create_re_radar(sp)


def get_token():
    token_valid = False
    token_info = session.get("token_info", {})

    if not (session.get('token_info', False)):
        token_valid = False
        return token_info, token_valid

    now = int(time.time())
    is_token_expired = session.get('token_info').get('expires_at') - now < 60

    if (is_token_expired):
        sp_oauth = create_spotify_oauth()
        token_info = sp_oauth.refresh_access_token(session.get('token_info').get('refresh_token'))

    token_valid = True
    return token_info, token_valid


def create_spotify_oauth(client_id=os.getenv('SPOTIPY_CLIENT_ID'), client_secret=os.getenv('SPOTIPY_CLIENT_SECRET')):

    return SpotifyOAuth(
        scope='playlist-modify-public,playlist-modify-private,user-library-read',
        redirect_uri=url_for('authorize', _external=True),
        client_id=client_id,
        client_secret=client_secret,
        cache_path='/tmp/.cache'
    )

if __name__ == '__main__':
    app.run()