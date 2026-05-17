"""Tests for issue #21: verify legacy provider cleanup is complete."""

import subprocess


class TestNoLegacyReferences:
    """Behavior 1: no legacy provider references remain in source."""

    def test_no_yfinance_in_source(self):
        result = subprocess.run(
            ["grep", "-r", "--include=*.py", "--exclude=test_cleanup.py",
             "yfinance", "app/", "tests/", "scripts/"],
            capture_output=True, text=True,
        )
        assert result.returncode != 0, (
            f"Legacy references still present:\n{result.stdout}"
        )

    def test_no_yahoo_provider_import(self):
        result = subprocess.run(
            ["grep", "-r", "--include=*.py", "--exclude=test_cleanup.py",
             "YahooFinanceProvider", "app/", "tests/"],
            capture_output=True, text=True,
        )
        assert result.returncode != 0, (
            f"Legacy references still present:\n{result.stdout}"
        )


class TestNoFinnhubReferences:
    """Behavior 2: no Finnhub references remain in source."""

    def test_no_finnhub_in_source(self):
        result = subprocess.run(
            ["grep", "-ri", "--include=*.py", "--exclude=test_cleanup.py",
             "finnhub", "app/", "tests/", "scripts/"],
            capture_output=True, text=True,
        )
        assert result.returncode != 0, (
            f"Finnhub references still present:\n{result.stdout}"
        )


class TestNoLegacyDeps:
    """Behavior 3: pyproject.toml has no yfinance or finnhub-python."""

    def test_no_yfinance_dep(self):
        result = subprocess.run(
            ["grep", "-i", "yfinance", "pyproject.toml"],
            capture_output=True, text=True,
        )
        assert result.returncode != 0, (
            f"yfinance still in pyproject.toml:\n{result.stdout}"
        )

    def test_no_finnhub_dep(self):
        result = subprocess.run(
            ["grep", "-i", "finnhub", "pyproject.toml"],
            capture_output=True, text=True,
        )
        assert result.returncode != 0, (
            f"finnhub-python still in pyproject.toml:\n{result.stdout}"
        )


class TestDeletedFiles:
    """Behavior 4: legacy files are deleted."""

    def test_fetch_settlement_prices_deleted(self):
        from pathlib import Path

        assert not Path("scripts/fetch_settlement_prices.py").exists()

    def test_yahoo_provider_deleted(self):
        from pathlib import Path

        assert not Path("app/providers/yahoo.py").exists()

    def test_finnhub_provider_deleted(self):
        from pathlib import Path

        assert not Path("app/providers/news.py").exists()


class TestConfigCleanup:
    """Behavior 5: config no longer exposes finnhub_api_key."""

    def test_no_finnhub_api_key_in_settings(self):
        from app.config import Settings

        s = Settings()
        assert not hasattr(s, "finnhub_api_key")


class TestAVWiring:
    """Behavior 6: server.py and cron.py use AV adapters."""

    def test_server_imports_av_adapters(self):
        result = subprocess.run(
            ["grep", "-c", r"AVMarketDataAdapter\|AVOptionsAdapter\|AVNewsAdapter",
             "app/server.py"],
            capture_output=True, text=True,
        )
        assert int(result.stdout.strip()) >= 3

    def test_cron_imports_av_adapters(self):
        result = subprocess.run(
            ["grep", "-c", r"AVMarketDataAdapter\|AVOptionsAdapter\|AVClient",
             "cron.py"],
            capture_output=True, text=True,
        )
        assert int(result.stdout.strip()) >= 3
