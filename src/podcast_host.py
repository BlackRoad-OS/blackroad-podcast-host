#!/usr/bin/env python3
"""
BlackRoad Podcast Host
Production module for managing podcasts, episodes, and generating RSS feeds.
"""

import sqlite3
import json
import sys
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, List
import xml.etree.ElementTree as ET

GREEN = '\033[0;32m'
RED = '\033[0;31m'
CYAN = '\033[0;36m'
YELLOW = '\033[1;33m'
NC = '\033[0m'

DB_PATH = os.path.expanduser("~/.blackroad/podcast_host.db")


@dataclass
class Episode:
    title: str
    description: str
    audio_file: str
    duration_s: int = 0
    published_at: Optional[str] = None
    season: int = 1
    episode_num: int = 1
    tags: str = ""
    podcast_id: Optional[int] = None
    id: Optional[int] = None
    created_at: Optional[str] = None


@dataclass
class Podcast:
    title: str
    description: str
    author: str
    email: str = ""
    language: str = "en"
    category: str = "Technology"
    website_url: str = ""
    image_url: str = ""
    explicit: bool = False
    id: Optional[int] = None
    created_at: Optional[str] = None


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS podcasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE NOT NULL,
            description TEXT,
            author TEXT NOT NULL,
            email TEXT DEFAULT '',
            language TEXT DEFAULT 'en',
            category TEXT DEFAULT 'Technology',
            website_url TEXT DEFAULT '',
            image_url TEXT DEFAULT '',
            explicit INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS episodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            podcast_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            audio_file TEXT NOT NULL,
            duration_s INTEGER DEFAULT 0,
            published_at TEXT,
            season INTEGER DEFAULT 1,
            episode_num INTEGER DEFAULT 1,
            tags TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (podcast_id) REFERENCES podcasts(id)
        )
    """)
    conn.commit()
    conn.close()


class PodcastHost:
    def __init__(self):
        init_db()
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        self.conn.close()

    def create_podcast(self, podcast: Podcast) -> Podcast:
        podcast.created_at = datetime.utcnow().isoformat()
        c = self.conn.cursor()
        try:
            c.execute("""
                INSERT INTO podcasts (title, description, author, email, language,
                    category, website_url, image_url, explicit, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (podcast.title, podcast.description, podcast.author, podcast.email,
                  podcast.language, podcast.category, podcast.website_url,
                  podcast.image_url, int(podcast.explicit), podcast.created_at))
            self.conn.commit()
            podcast.id = c.lastrowid
            print(f"{GREEN}✓ Created podcast: {podcast.title}{NC}")
        except sqlite3.IntegrityError:
            print(f"{YELLOW}⚠ Podcast '{podcast.title}' already exists{NC}")
        return podcast

    def add_episode(self, episode: Episode) -> Episode:
        episode.created_at = datetime.utcnow().isoformat()
        if not episode.published_at:
            episode.published_at = episode.created_at
        c = self.conn.cursor()
        c.execute("""
            INSERT INTO episodes (podcast_id, title, description, audio_file,
                duration_s, published_at, season, episode_num, tags, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (episode.podcast_id, episode.title, episode.description, episode.audio_file,
              episode.duration_s, episode.published_at, episode.season,
              episode.episode_num, episode.tags, episode.created_at))
        self.conn.commit()
        episode.id = c.lastrowid
        print(f"{GREEN}✓ Added episode S{episode.season:02d}E{episode.episode_num:02d}: "
              f"{episode.title}{NC}")
        return episode

    def list_episodes(self, podcast_id: Optional[int] = None,
                      podcast_title: Optional[str] = None) -> List[Episode]:
        c = self.conn.cursor()
        pid = podcast_id
        if not pid and podcast_title:
            c.execute("SELECT id FROM podcasts WHERE title = ?", (podcast_title,))
            row = c.fetchone()
            pid = row["id"] if row else None

        if pid:
            c.execute("""
                SELECT * FROM episodes WHERE podcast_id = ?
                ORDER BY season, episode_num
            """, (pid,))
        else:
            c.execute("SELECT * FROM episodes ORDER BY podcast_id, season, episode_num")

        return [self._row_to_episode(r) for r in c.fetchall()]

    def _row_to_episode(self, r) -> Episode:
        return Episode(id=r["id"], podcast_id=r["podcast_id"], title=r["title"],
                       description=r["description"], audio_file=r["audio_file"],
                       duration_s=r["duration_s"], published_at=r["published_at"],
                       season=r["season"], episode_num=r["episode_num"],
                       tags=r["tags"], created_at=r["created_at"])

    def _row_to_podcast(self, r) -> Podcast:
        return Podcast(id=r["id"], title=r["title"], description=r["description"],
                       author=r["author"], email=r["email"], language=r["language"],
                       category=r["category"], website_url=r["website_url"],
                       image_url=r["image_url"], explicit=bool(r["explicit"]),
                       created_at=r["created_at"])

    def generate_rss_feed(self, podcast_title: str,
                          output_path: Optional[str] = None) -> str:
        c = self.conn.cursor()
        c.execute("SELECT * FROM podcasts WHERE title = ?", (podcast_title,))
        prow = c.fetchone()
        if not prow:
            print(f"{RED}✗ Podcast not found: {podcast_title}{NC}")
            return ""

        podcast = self._row_to_podcast(prow)
        episodes = self.list_episodes(podcast_id=podcast.id)

        # Build RSS XML
        rss = ET.Element("rss", version="2.0")
        rss.set("xmlns:itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
        rss.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")

        channel = ET.SubElement(rss, "channel")

        ET.SubElement(channel, "title").text = podcast.title
        ET.SubElement(channel, "description").text = podcast.description
        ET.SubElement(channel, "language").text = podcast.language
        ET.SubElement(channel, "link").text = podcast.website_url or "https://blackroad.io"
        ET.SubElement(channel, "itunes:author").text = podcast.author
        ET.SubElement(channel, "itunes:explicit").text = "yes" if podcast.explicit else "no"

        owner = ET.SubElement(channel, "itunes:owner")
        ET.SubElement(owner, "itunes:name").text = podcast.author
        ET.SubElement(owner, "itunes:email").text = podcast.email

        cat = ET.SubElement(channel, "itunes:category")
        cat.set("text", podcast.category)

        if podcast.image_url:
            img = ET.SubElement(channel, "itunes:image")
            img.set("href", podcast.image_url)

        for ep in episodes:
            item = ET.SubElement(channel, "item")
            ET.SubElement(item, "title").text = ep.title
            ET.SubElement(item, "description").text = ep.description or ""
            ET.SubElement(item, "pubDate").text = ep.published_at or ""
            ET.SubElement(item, "itunes:duration").text = str(ep.duration_s)
            ET.SubElement(item, "itunes:season").text = str(ep.season)
            ET.SubElement(item, "itunes:episode").text = str(ep.episode_num)
            if ep.tags:
                ET.SubElement(item, "itunes:keywords").text = ep.tags

            enc = ET.SubElement(item, "enclosure")
            enc.set("url", ep.audio_file)
            enc.set("type", "audio/mpeg")
            enc.set("length", "0")

            guid = ET.SubElement(item, "guid")
            guid.text = f"{podcast.website_url}/episodes/s{ep.season:02d}e{ep.episode_num:02d}"
            guid.set("isPermaLink", "false")

        tree = ET.ElementTree(rss)
        output_path = output_path or f"/tmp/{podcast_title.lower().replace(' ', '_')}_rss.xml"
        ET.indent(tree, space="  ")
        tree.write(output_path, encoding="unicode", xml_declaration=True)
        print(f"{GREEN}✓ RSS feed generated: {output_path} "
              f"({len(episodes)} episodes){NC}")
        return output_path

    def export_stats(self, output_path: str = "/tmp/podcast_stats.json"):
        c = self.conn.cursor()
        c.execute("SELECT * FROM podcasts")
        podcasts = [self._row_to_podcast(r) for r in c.fetchall()]
        stats = []
        for p in podcasts:
            episodes = self.list_episodes(podcast_id=p.id)
            total_duration = sum(e.duration_s for e in episodes)
            stats.append({
                "podcast": asdict(p),
                "episode_count": len(episodes),
                "total_duration_s": total_duration,
                "total_duration_hrs": round(total_duration / 3600, 2),
                "seasons": list(set(e.season for e in episodes)),
                "latest_episode": max(
                    (e.published_at for e in episodes), default=None
                )
            })
        data = {"podcasts": stats, "exported_at": datetime.utcnow().isoformat()}
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"{GREEN}✓ Stats exported to {output_path}{NC}")
        return output_path


def format_duration(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def main():
    host = PodcastHost()
    args = sys.argv[1:]
    if not args:
        print(f"{CYAN}BlackRoad Podcast Host{NC}")
        print("Commands: list [podcast], add-podcast, add-episode, rss, status, export")
        host.close()
        return
    cmd = args[0]
    rest = args[1:]
    if cmd == "list":
        title = rest[0] if rest else None
        episodes = host.list_episodes(podcast_title=title)
        if not episodes:
            print(f"{YELLOW}No episodes found.{NC}")
        else:
            print(f"\n{CYAN}=== Episodes ({len(episodes)}) ==={NC}")
            for e in episodes:
                dur = format_duration(e.duration_s)
                print(f"  S{e.season:02d}E{e.episode_num:02d} | "
                      f"{CYAN}{e.title}{NC} | {dur} | {e.published_at[:10] if e.published_at else 'unpublished'}")
    elif cmd == "add-podcast":
        if len(rest) < 3:
            print(f"{RED}Usage: add-podcast <title> <description> <author> [email]{NC}")
        else:
            p = Podcast(title=rest[0], description=rest[1], author=rest[2],
                        email=rest[3] if len(rest) > 3 else "")
            host.create_podcast(p)
    elif cmd == "add-episode":
        if len(rest) < 4:
            print(f"{RED}Usage: add-episode <podcast_id> <title> <audio_file> "
                  f"<duration_s> [season] [ep_num] [description]{NC}")
        else:
            e = Episode(podcast_id=int(rest[0]), title=rest[1], audio_file=rest[2],
                        duration_s=int(rest[3]),
                        description=rest[4] if len(rest) > 4 else rest[1],
                        season=int(rest[5]) if len(rest) > 5 else 1,
                        episode_num=int(rest[6]) if len(rest) > 6 else 1)
            host.add_episode(e)
    elif cmd == "rss":
        if not rest:
            print(f"{RED}Usage: rss <podcast_title> [output_path]{NC}")
        else:
            path = rest[1] if len(rest) > 1 else None
            host.generate_rss_feed(rest[0], path)
    elif cmd == "status":
        c = host.conn.cursor()
        c.execute("SELECT COUNT(*) as n FROM podcasts")
        pc = c.fetchone()["n"]
        c.execute("SELECT COUNT(*) as n FROM episodes")
        ec = c.fetchone()["n"]
        c.execute("SELECT SUM(duration_s) as total FROM episodes")
        td = c.fetchone()["total"] or 0
        print(f"\n{CYAN}=== Podcast Status ==={NC}")
        print(f"  Podcasts:      {pc}")
        print(f"  Episodes:      {ec}")
        print(f"  Total Runtime: {format_duration(int(td))}")
    elif cmd == "export":
        path = rest[0] if rest else "/tmp/podcast_stats.json"
        host.export_stats(path)
    else:
        print(f"{RED}Unknown command: {cmd}{NC}")
    host.close()


if __name__ == "__main__":
    main()
