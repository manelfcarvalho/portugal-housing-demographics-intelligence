"""Download JSON from a supplied official API URL, preserving response bytes."""

import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import logging
import math
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

import requests

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
RETRY_STATUSES = {429, 500, 502, 503, 504}
LOGGER = logging.getLogger(__name__)


def _retry_after(header: str | None) -> float:
    """Interpret Retry-After seconds or HTTP date without assuming it is valid."""
    if not header:
        return 0.0
    try:
        seconds = float(header)
        return max(0.0, seconds) if math.isfinite(seconds) else 0.0
    except ValueError:
        try:
            date = parsedate_to_datetime(header)
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            return max(0.0, (date - datetime.now(timezone.utc)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return 0.0


def fetch_ine(
    url: str,
    name: str,
    output_dir: Path = RAW_DIR,
    *,
    timeout: float = 30.0,
    max_retries: int = 3,
    backoff_factor: float = 1.0,
) -> Path:
    """Save valid JSON verbatim. max_retries excludes the initial attempt.

    Retry selected HTTP errors and connection/timeouts; permanent HTTP errors,
    invalid JSON and filesystem errors fail immediately. Never overwrite a file.
    """
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("Provide a complete HTTP(S) API URL.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
        raise ValueError("Name must start with a letter/digit and contain only letters, digits, _ or -.")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Timeout must be finite and greater than zero.")
    if not isinstance(max_retries, int) or max_retries < 0:
        raise ValueError("max_retries must be a non-negative integer.")
    if not math.isfinite(backoff_factor) or backoff_factor < 0:
        raise ValueError("backoff_factor must be finite and non-negative.")
    destination = Path(output_dir) / f"{name}.json"
    if destination.exists():
        raise FileExistsError(f"Raw file already exists; choose a new name: {destination}")

    for attempt in range(max_retries + 1):
        retry_after = 0.0
        try:
            with requests.get(url, timeout=timeout) as response:
                retry_after = _retry_after(response.headers.get("Retry-After"))
                response.raise_for_status()
                payload = response.content
                # Validate without reserializing: whitespace and source types survive.
                json.loads(payload)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status not in RETRY_STATUSES or attempt == max_retries:
                raise
            reason = f"HTTP {status}"
        except (requests.Timeout, requests.ConnectionError) as exc:
            if attempt == max_retries:
                raise
            reason = type(exc).__name__
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as handle:
                handle.write(payload)
            LOGGER.info("Saved unchanged JSON response to %s", destination)
            return destination

        delay = max(backoff_factor * (2 ** attempt), retry_after)
        LOGGER.warning("%s; retry %s/%s in %.1f seconds", reason, attempt + 1, max_retries, delay)
        time.sleep(delay)

    raise RuntimeError("Retry loop ended unexpectedly")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Real INE API URL, including validated filters")
    parser.add_argument("--name", required=True, help="Output filename without .json")
    parser.add_argument("--output-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--backoff-factor", type=float, default=1.0)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        fetch_ine(**vars(args))
    except (requests.RequestException, ValueError, OSError) as exc:
        parser.exit(1, f"Extraction failed: {exc}\n")


if __name__ == "__main__":
    main()
