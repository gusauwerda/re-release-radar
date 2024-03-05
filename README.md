# Re-release Radar

### I was sick of the only good Spotify generated playlist appearing just once per week, and with a multitude of songs I'd already liked.

#### Features
- A playlist that is automatically updated and pushed to signed up users, once per hour, based on their individual recommendations.
- A direct link to manually refresh your playlist

#### Design decisions
- The seed tracks used in playlist generation are stored for 24 hours, then themselves refreshed. Spotify rate limits API requests, and refreshing the seed tracks for every playlist refresh was maxxing it out.
