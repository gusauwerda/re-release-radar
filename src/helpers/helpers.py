from spotipy import Spotify


class Helpers:

    authentication: Spotify

    def __init__(self, authentication):
        self.authentication = authentication

    def get_all_liked_songs(self, page=0):
        limit = 50
        offset = limit * page

        sp = self.authentication.get_sp()
        tracks = sp.current_user_saved_tracks(limit=limit, offset=offset)["items"]

        spotify_ids = [item["track"]["id"] for item in tracks]

        if len(spotify_ids) == 50:
            self.get_all_liked_songs(page + 1)

        return spotify_ids, tracks

    def get_seed_tracks(self, sp, number_of_tracks):
        track_ids = []

        if sp == None:
            sp = self.authentication.get_sp()
        tracks = sp.current_user_saved_tracks(limit=number_of_tracks)
        for track in tracks["items"]:
            track_ids.append(track["track"]["id"])
        return track_ids
