from spotipy import Spotify

class Playlist:

    authentication: Spotify

    def __init__(self, authentication):
        self.authentication = authentication

    def update(self, sp, playlist_id, track_ids):
        if sp == None:
            sp = self.authentication.get_sp()
        sp.playlist_replace_items(playlist_id=playlist_id, items=track_ids)

    def get_or_create(self, sp, playlist_name, playlist_description):
        if sp == None:
            sp = self.authentication.get_sp()

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
