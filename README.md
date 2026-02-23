# blackroad-podcast-host

A self-hosted podcast management platform that stores episodes and podcasts in a local SQLite database and generates standards-compliant iTunes/RSS feeds ready for submission to Apple Podcasts, Spotify, and any other RSS-based directory.

The RSS generator builds a fully-spec-compliant `<channel>` with `itunes:*` namespace tags, per-episode `<item>` blocks with `<enclosure>`, GUID, season, and episode number fields. Audio files can be hosted anywhere — S3, R2, Cloudflare CDN, or a plain HTTP server — just pass the URL when adding an episode.

Part of the **BlackRoad OS** developer toolchain — combine with a Cloudflare Worker to serve the feed at your custom domain.

## Features

- **Multi-podcast support** — manage multiple shows from one database
- **Episode management** — title, description, audio URL, duration, season/episode numbering, tags
- **iTunes-compliant RSS** — `xmlns:itunes` namespace, owner block, category, explicit flag, per-episode keywords
- **Episode ordering** — sorted by season then episode number
- **Stats export** — episode count, total runtime, season list, latest publish date per podcast
- **SQLite persistence** — `~/.blackroad/podcast_host.db`
- **CLI interface** — `add-podcast`, `add-episode`, `list`, `rss`, `status`, `export`

## Installation

```bash
git clone https://github.com/BlackRoad-OS/blackroad-podcast-host.git
cd blackroad-podcast-host
python3 src/podcast_host.py
```

Run the test suite:

```bash
pip install pytest
pytest tests/ -v
```

## Usage

```bash
# Create a podcast
python3 src/podcast_host.py add-podcast \
    "BlackRoad Dev Talks" \
    "Weekly deep-dives into the BlackRoad OS platform." \
    "Alexa" \
    "podcast@blackroad.io"

# Add an episode: podcast_id title audio_url duration_s [description season ep_num]
python3 src/podcast_host.py add-episode 1 \
    "Intro to the Agent System" \
    "https://cdn.blackroad.io/ep001.mp3" \
    3600

python3 src/podcast_host.py add-episode 1 \
    "Building Tokenless Gateways" \
    "https://cdn.blackroad.io/ep002.mp3" \
    2847 \
    "How the BlackRoad gateway keeps secrets out of agents" 1 2

# List all episodes
python3 src/podcast_host.py list
python3 src/podcast_host.py list "BlackRoad Dev Talks"

# Generate RSS feed
python3 src/podcast_host.py rss "BlackRoad Dev Talks"
python3 src/podcast_host.py rss "BlackRoad Dev Talks" /var/www/feed.xml

# Dashboard status
python3 src/podcast_host.py status

# Export stats JSON
python3 src/podcast_host.py export /tmp/podcast_stats.json
```

### Example list output

```
=== Episodes (2) ===
  S01E01 | Intro to the Agent System           | 01:00:00 | 2024-07-15
  S01E02 | Building Tokenless Gateways         | 00:47:27 | 2024-07-22
```

## API

### `Podcast`

| Field | Type | Description |
|---|---|---|
| `title` | `str` | Unique podcast title |
| `description` | `str` | Show description |
| `author` | `str` | Host name |
| `email` | `str` | Contact email for iTunes |
| `category` | `str` | iTunes top-level category |
| `explicit` | `bool` | Explicit content flag |

### `Episode`

| Field | Type | Description |
|---|---|---|
| `podcast_id` | `int` | Foreign key to parent podcast |
| `title` | `str` | Episode title |
| `audio_file` | `str` | URL to audio file |
| `duration_s` | `int` | Duration in seconds |
| `season` | `int` | Season number |
| `episode_num` | `int` | Episode number within season |

### `PodcastHost`

| Method | Description |
|---|---|
| `create_podcast(p)` | Register a new podcast |
| `add_episode(e)` | Add an episode to a podcast |
| `list_episodes(podcast_id, podcast_title)` | List episodes ordered by S/E |
| `generate_rss_feed(title, output_path)` | Write iTunes RSS XML file |
| `export_stats(path)` | Write JSON stats for all podcasts |

## License

MIT © BlackRoad OS, Inc.
