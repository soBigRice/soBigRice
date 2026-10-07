import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("refresh_profile", Path(__file__).resolve().parents[1] / "scripts/refresh_profile.py")
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)


def repo(fork=False, languages=None):
    return {"fork": fork, "private": False, "visibility": "public", "stars": 4,
            "forks": 1, "languages": languages or {}, "releases": []}


class PublicProfileTests(unittest.TestCase):
    def test_fork_stars_count_but_fork_code_is_not_attributed_to_original_work(self):
        original = repo(languages={"JavaScript": 100})
        fork = repo(fork=True, languages={"C": 900_000})
        fork["stars"] = 8
        summary = profile.summarize({"repositories": [original, fork]})
        self.assertEqual(summary["stars"], 12)
        self.assertEqual(summary["languages"], {"JavaScript": 100})
        self.assertEqual(summary["original_repos"], 1)
        self.assertEqual(summary["fork_repos"], 1)

    def test_non_public_repositories_are_rejected(self):
        for field, value in (("private", True), ("visibility", "private")):
            candidate = repo()
            candidate[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                profile.summarize({"repositories": [candidate]})

    def test_draft_release_downloads_are_excluded_and_published_dates_order_versions(self):
        releases = [
            {"tag_name": "draft", "draft": True, "published_at": "2026-10-07T10:00:00Z",
             "html_url": "https://github.com/example/draft", "prerelease": False,
             "assets": [{"download_count": 999}]},
            {"tag_name": "v1", "draft": False, "published_at": "2026-10-05T10:00:00Z",
             "html_url": "https://github.com/example/v1", "prerelease": False,
             "assets": [{"download_count": 2}]},
            {"tag_name": "v2-beta", "draft": False, "published_at": "2026-10-06T10:00:00Z",
             "html_url": "https://github.com/example/v2-beta", "prerelease": True,
             "assets": [{"download_count": 3}]},
        ]
        public = profile.public_releases(releases)
        self.assertEqual([r["tag"] for r in public], ["v2-beta", "v1"])
        self.assertEqual(sum(r["downloads"] for r in public), 5)

    def test_description_cannot_create_a_new_table_column_or_html_control(self):
        self.assertEqual(profile.cell('a|b\n<script>'), 'a\\|b &lt;script&gt;')

    def test_missing_markers_do_not_overwrite_readme_or_create_partial_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            readme = root / "README.md"
            readme.write_text("existing readme\n")
            data = {"repositories": [], "snapshot_date": "2026-10-07", "user": {
                "followers": 1, "following": 2, "public_gists": 0, "created_at": "2020-04-10T00:00:00Z"}}
            with patch.object(profile, "ROOT", root), self.assertRaises(ValueError):
                profile.render(data)
            self.assertEqual(readme.read_text(), "existing readme\n")
            self.assertFalse((root / "assets").exists())


if __name__ == "__main__":
    unittest.main()
