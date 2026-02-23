#!/usr/bin/env python3
"""Tests for BlackRoad Podcast Host."""

import os
import sys
import json
import sqlite3
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import podcast_host as ph


def _make_tmp_db():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    return f.name


class TestPodcastDataclass(unittest.TestCase):
    def test_podcast_defaults(self):
        p = ph.Podcast(title="My Show", description="A show", author="Alice")
        self.assertEqual(p.language, "en")
        self.assertEqual(p.category, "Technology")
        self.assertFalse(p.explicit)
        self.assertIsNone(p.id)

    def test_episode_defaults(self):
        e = ph.Episode(
            title="Ep 1", description="desc",
            audio_file="s3://bucket/ep1.mp3",
        )
        self.assertEqual(e.season, 1)
        self.assertEqual(e.episode_num, 1)
        self.assertEqual(e.duration_s, 0)
        self.assertIsNone(e.id)


class TestInitDb(unittest.TestCase):
    def test_tables_created(self):
        path = _make_tmp_db()
        try:
            ph.DB_PATH = path
            ph.init_db()
            conn = sqlite3.connect(path)
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            conn.close()
            self.assertIn("podcasts", tables)
            self.assertIn("episodes", tables)
        finally:
            os.unlink(path)

    def test_init_idempotent(self):
        path = _make_tmp_db()
        try:
            ph.DB_PATH = path
            ph.init_db()
            ph.init_db()
        finally:
            os.unlink(path)


class TestPodcastHost(unittest.TestCase):
    def setUp(self):
        self.path = _make_tmp_db()
        ph.DB_PATH = self.path
        self.host = ph.PodcastHost()

    def tearDown(self):
        self.host.close()
        os.unlink(self.path)

    def _podcast(self, title="Tech Talks"):
        return ph.Podcast(
            title=title, description="All about tech", author="Bob",
            email="bob@example.com", website_url="https://techtalk.io",
        )

    def _episode(self, pid, num=1):
        return ph.Episode(
            podcast_id=pid, title=f"Episode {num}",
            description="Great stuff", audio_file=f"https://cdn.io/ep{num}.mp3",
            duration_s=3600, season=1, episode_num=num,
        )

    def test_create_podcast_assigns_id(self):
        p = self.host.create_podcast(self._podcast())
        self.assertIsNotNone(p.id)
        self.assertGreater(p.id, 0)

    def test_create_podcast_sets_created_at(self):
        p = self.host.create_podcast(self._podcast())
        self.assertIsNotNone(p.created_at)

    def test_create_duplicate_podcast_no_exception(self):
        self.host.create_podcast(self._podcast("Dup Show"))
        self.host.create_podcast(self._podcast("Dup Show"))

    def test_add_episode_assigns_id(self):
        p = self.host.create_podcast(self._podcast())
        e = self.host.add_episode(self._episode(p.id))
        self.assertIsNotNone(e.id)

    def test_add_episode_sets_published_at(self):
        p = self.host.create_podcast(self._podcast())
        e = self.host.add_episode(self._episode(p.id))
        self.assertIsNotNone(e.published_at)

    def test_list_episodes_empty(self):
        self.assertEqual(self.host.list_episodes(), [])

    def test_list_episodes_by_podcast_title(self):
        p = self.host.create_podcast(self._podcast("Filtered Show"))
        self.host.add_episode(self._episode(p.id, 1))
        self.host.add_episode(self._episode(p.id, 2))
        episodes = self.host.list_episodes(podcast_title="Filtered Show")
        self.assertEqual(len(episodes), 2)

    def test_list_episodes_ordered_by_season_and_num(self):
        p = self.host.create_podcast(self._podcast("Ordered"))
        self.host.add_episode(ph.Episode(
            podcast_id=p.id, title="E2", description="d",
            audio_file="a.mp3", season=1, episode_num=2,
        ))
        self.host.add_episode(ph.Episode(
            podcast_id=p.id, title="E1", description="d",
            audio_file="b.mp3", season=1, episode_num=1,
        ))
        episodes = self.host.list_episodes(podcast_id=p.id)
        self.assertEqual(episodes[0].episode_num, 1)
        self.assertEqual(episodes[1].episode_num, 2)

    def test_generate_rss_feed_creates_file(self):
        p = self.host.create_podcast(self._podcast("RSS Show"))
        self.host.add_episode(self._episode(p.id))
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
            path = f.name
        try:
            result = self.host.generate_rss_feed("RSS Show", path)
            self.assertEqual(result, path)
            self.assertTrue(os.path.getsize(path) > 0)
        finally:
            os.unlink(path)

    def test_rss_feed_valid_xml(self):
        p = self.host.create_podcast(self._podcast("Valid XML"))
        self.host.add_episode(self._episode(p.id))
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
            path = f.name
        try:
            self.host.generate_rss_feed("Valid XML", path)
            tree = ET.parse(path)
            root = tree.getroot()
            self.assertEqual(root.tag, "rss")
        finally:
            os.unlink(path)

    def test_rss_contains_episode_items(self):
        p = self.host.create_podcast(self._podcast("Multi Ep"))
        self.host.add_episode(self._episode(p.id, 1))
        self.host.add_episode(self._episode(p.id, 2))
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
            path = f.name
        try:
            self.host.generate_rss_feed("Multi Ep", path)
            tree = ET.parse(path)
            items = tree.findall(".//item")
            self.assertEqual(len(items), 2)
        finally:
            os.unlink(path)

    def test_rss_missing_podcast_returns_empty(self):
        result = self.host.generate_rss_feed("Nonexistent", "/tmp/nope.xml")
        self.assertEqual(result, "")

    def test_export_stats_structure(self):
        p = self.host.create_podcast(self._podcast("Stats Show"))
        self.host.add_episode(self._episode(p.id))
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            self.host.export_stats(path)
            with open(path) as f:
                data = json.load(f)
            self.assertIn("podcasts", data)
            self.assertEqual(data["podcasts"][0]["episode_count"], 1)
        finally:
            os.unlink(path)

    def test_format_duration_helper(self):
        self.assertEqual(ph.format_duration(3661), "01:01:01")
        self.assertEqual(ph.format_duration(0), "00:00:00")
        self.assertEqual(ph.format_duration(7200), "02:00:00")


if __name__ == "__main__":
    unittest.main()
