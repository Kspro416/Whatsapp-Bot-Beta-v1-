"""
bot_logic.py  v8  (final)
Fix: _wait_for_main_load now checks for header/footer in #main,
     which appear as soon as a chat opens — even before messages render.
"""

import threading
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
    ElementClickInterceptedException,
)
from selenium.webdriver.common.action_chains import ActionChains

LOADED_INDICATORS = [
    '#side',
    'div[aria-label="Chat list"]',
    '[data-testid="chat-list"]',
]

COMPOSE_SELECTORS = [
    'div[data-testid="conversation-compose-box-input"]',
    'div[contenteditable="true"][data-tab="10"]',
    'div[role="textbox"][data-tab="10"]',
    'footer div[contenteditable="true"]',
    '#main div[contenteditable="true"]',
    'div[aria-label="Type a message"]',
    'div[title="Type a message"]',
]

OLLAMA_API_URL = "http://localhost:11434/api/generate"
WHATSAPP_URL   = "https://web.whatsapp.com"
HEARTBEAT_SECS = 20
POLL_INTERVAL  = 2


class WhatsAppBot:
    def __init__(self, log_callback, status_callback,
                 profile_path="", headless=False,
                 system_prompt="You are a helpful assistant.",
                 ollama_model="phi3"):
        self._log    = log_callback
        self._status = status_callback
        self.profile_path  = profile_path
        self.headless       = headless
        self.system_prompt  = system_prompt
        self.ollama_model   = ollama_model
        self.driver          = None
        self._stop_event     = threading.Event()
        self._main_thread    = None
        self._hb_thread      = None
        self._processed: set = set()

    # ── Public ────────────────────────────────────────────────────────────────

    def start(self):
        self._stop_event.clear()
        self._main_thread = threading.Thread(target=self._run, daemon=True)
        self._main_thread.start()

    def stop(self):
        self._stop_event.set()
        self._status("Stopping…")
        self._log("⏹  Stop signal sent.")

    def update_system_prompt(self, p):
        self.system_prompt = p

    def is_running(self):
        return self._main_thread is not None and self._main_thread.is_alive()

    # ── Driver ────────────────────────────────────────────────────────────────

    def _build_driver(self):
        opts = Options()
        opts.add_argument("--window-size=1920,1080")
        opts.add_argument("--disable-notifications")
        opts.add_argument("--disable-infobars")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        if self.headless:
            opts.add_argument("--headless=new")
        if self.profile_path:
            opts.add_argument(f"--user-data-dir={self.profile_path}")
        driver = webdriver.Chrome(options=opts)
        driver.execute_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
        )
        return driver

    # ── Main loop ─────────────────────────────────────────────────────────────

    def _run(self):
        try:
            self._log("🚀  Launching Chrome…")
            self._status("Launching browser")
            self.driver = self._build_driver()
            self.driver.get(WHATSAPP_URL)

            self._log("⏳  Waiting for WhatsApp Web…")
            self._status("Loading WhatsApp Web")
            self._wait_for_initial_load(timeout=90)

            if self._is_qr_screen():
                self._log("📱  QR shown — please scan.")
                self._status("⚡ Scan QR code on phone")
                self._wait_for_login(timeout=120)
            else:
                self._log("✅  Session restored.")

            self._log("⌛  Waiting for chat list…")
            self._wait_for_chat_list(timeout=60)
            time.sleep(2)
            self._log("✅  Ready. Monitoring for messages…")
            self._status("Running ✔")

            self._hb_thread = threading.Thread(target=self._heartbeat, daemon=True)
            self._hb_thread.start()

            while not self._stop_event.is_set():
                try:
                    self._scan_for_unread()
                except (StaleElementReferenceException, TimeoutException):
                    pass
                except Exception as e:
                    self._log(f"⚠️  Poll error: {e}")
                self._stop_event.wait(POLL_INTERVAL)

        except WebDriverException as e:
            self._log(f"❌  Browser error: {e}")
            self._status("Browser error")
        except Exception as e:
            self._log(f"❌  Fatal: {e}")
            self._status("Error")
        finally:
            self._cleanup()

    # ── Load / login ──────────────────────────────────────────────────────────

    def _wait_for_initial_load(self, timeout=90):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._stop_event.is_set():
                return
            try:
                if self.driver.find_elements(By.CSS_SELECTOR, "canvas"):
                    return
                for sel in LOADED_INDICATORS:
                    if self.driver.find_elements(By.CSS_SELECTOR, sel):
                        return
            except WebDriverException:
                pass
            time.sleep(1.5)
        raise TimeoutException("WA Web did not load.")

    def _is_qr_screen(self):
        try:
            for sel in LOADED_INDICATORS:
                if self.driver.find_elements(By.CSS_SELECTOR, sel):
                    return False
            return bool(self.driver.find_elements(By.CSS_SELECTOR, "canvas"))
        except Exception:
            return False

    def _wait_for_login(self, timeout=120):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._stop_event.is_set():
                return
            for sel in LOADED_INDICATORS:
                try:
                    if self.driver.find_elements(By.CSS_SELECTOR, sel):
                        self._log("✅  Logged in.")
                        return
                except Exception:
                    pass
            time.sleep(2)
        raise TimeoutException("QR scan timeout.")

    def _wait_for_chat_list(self, timeout=60):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._stop_event.is_set():
                return
            try:
                if self.driver.find_elements(By.CSS_SELECTOR, '[data-testid^="list-item-"]'):
                    return
            except Exception:
                pass
            time.sleep(1)

    # ── Unread scan ───────────────────────────────────────────────────────────

    def _scan_for_unread(self):
        try:
            badges = self.driver.find_elements(
                By.CSS_SELECTOR, '[data-testid="icon-unread-count"]'
            )
        except Exception:
            return

        if not badges:
            return

        rows = []
        seen = set()
        for badge in badges:
            try:
                row = self.driver.execute_script(
                    """
                    try {
                        var el = arguments[0];
                        while (el && el !== document.body) {
                            var tid = el.getAttribute('data-testid') || '';
                            if (tid.startsWith('list-item-')) return el;
                            el = el.parentElement;
                        }
                        return null;
                    } catch(e) { return null; }
                    """,
                    badge
                )
                if row:
                    tid = row.get_attribute("data-testid")
                    if tid not in seen:
                        seen.add(tid)
                        rows.append(row)
            except (StaleElementReferenceException, Exception):
                continue

        if not rows:
            return

        self._log(f"🔍  {len(rows)} unread chat(s) detected.")

        for row in rows[:5]:
            if self._stop_event.is_set():
                break
            try:
                chat_name = self._get_row_name(row)

                if not self._click_chat_row(row):
                    self._log(f"⚠️  [{chat_name}] All click methods failed.")
                    continue

                if not self._wait_for_main_load(timeout=12):
                    self._log(f"⚠️  [{chat_name}] Chat panel did not load after click.")
                    continue

                self._handle_open_chat(chat_name)

            except StaleElementReferenceException:
                continue
            except Exception as e:
                self._log(f"⚠️  Row error: {e}")

    def _get_row_name(self, row) -> str:
        try:
            el = row.find_element(By.CSS_SELECTOR, '[data-testid="cell-frame-title"]')
            lines = [l.strip() for l in el.text.strip().splitlines() if l.strip()]
            return lines[-1] if lines else "Unknown"
        except Exception:
            return "Unknown"

    def _click_chat_row(self, row) -> bool:
        # Strategy 1: native Selenium click on cell-frame-container
        try:
            cell = row.find_element(By.CSS_SELECTOR, '[data-testid="cell-frame-container"]')
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", cell)
            time.sleep(0.3)
            cell.click()
            return True
        except (NoSuchElementException, ElementClickInterceptedException, Exception):
            pass

        # Strategy 2: ActionChains
        try:
            cell = row.find_element(By.CSS_SELECTOR, '[data-testid="cell-frame-container"]')
            ActionChains(self.driver).move_to_element(cell).click().perform()
            return True
        except Exception:
            pass

        # Strategy 3: click the row itself
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", row)
            time.sleep(0.3)
            row.click()
            return True
        except Exception:
            pass

        return False

    def _wait_for_main_load(self, timeout=12) -> bool:
        """
        Returns True as soon as #main contains a header or footer —
        both appear immediately when any chat is opened in WA Web.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                # Check via Selenium directly — avoids JS string quoting issues
                main_els = self.driver.find_elements(By.CSS_SELECTOR, "#main header")
                if main_els:
                    return True
                footer_els = self.driver.find_elements(By.CSS_SELECTOR, "#main footer")
                if footer_els:
                    return True
                compose_els = self.driver.find_elements(By.CSS_SELECTOR, "#main [contenteditable]")
                if compose_els:
                    return True
            except Exception:
                pass
            time.sleep(0.4)
        return False

    # ── Chat handling ─────────────────────────────────────────────────────────

    def _handle_open_chat(self, chat_name="Unknown"):
        # Extra small wait for messages to render after header appears
        time.sleep(0.8)

        last_msg = self._get_last_inbound_message()

        if not last_msg:
            self._log(f"ℹ️  [{chat_name}] No inbound message text found.")
            return

        key = f"{chat_name}::{last_msg[:120]}"
        if key in self._processed:
            self._log(f"⏭  [{chat_name}] Already replied — skipping.")
            return
        self._processed.add(key)
        if len(self._processed) > 500:
            self._processed = set(list(self._processed)[-250:])

        self._log(f"📨  [{chat_name}] Received: {last_msg[:80]}")

        reply = self._query_ollama(last_msg)
        if not reply:
            self._log("⚠️  Empty AI reply — skipping.")
            return

        self._log(f"🤖  [{chat_name}] Replying: {reply[:80]}")
        if self._send_message(reply):
            self._log(f"✅  [{chat_name}] Sent.")
            # Close the chat so WA marks future incoming messages as unread
            time.sleep(0.5)
            self._close_active_chat()
        else:
            self._log(f"❌  [{chat_name}] Could not find compose box.")

    def _get_last_inbound_message(self) -> str:
        try:
            return self.driver.execute_script(
                """
                try {
                    var inMsgs = document.querySelectorAll('div.message-in');
                    if (inMsgs.length) {
                        var last = inMsgs[inMsgs.length - 1];
                        var spans = last.querySelectorAll('span.selectable-text');
                        for (var i = spans.length - 1; i >= 0; i--) {
                            var t = (spans[i].innerText || '').trim();
                            if (t) return t;
                        }
                        var dirSpans = last.querySelectorAll('span[dir]');
                        for (var i = dirSpans.length - 1; i >= 0; i--) {
                            var t = (dirSpans[i].innerText || '').trim();
                            if (t) return t;
                        }
                        return (last.innerText || '').trim();
                    }
                    var copyable = document.querySelectorAll('#main [class*="copyable-text"]');
                    for (var i = copyable.length - 1; i >= 0; i--) {
                        var t = (copyable[i].innerText || '').trim();
                        if (t && t.length < 3000) return t;
                    }
                    return '';
                } catch(e) { return ''; }
                """
            ) or ""
        except Exception as e:
            self._log(f"⚠️  Msg extract error: {e}")
            return ""

    # ── Send ──────────────────────────────────────────────────────────────────

    def _send_message(self, text: str) -> bool:
        # Step 1: find and focus the compose box
        box = None
        for sel in COMPOSE_SELECTORS:
            try:
                box = WebDriverWait(self.driver, 8).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", box)
                time.sleep(0.2)
                box.click()
                time.sleep(0.3)
                break
            except (TimeoutException, NoSuchElementException):
                box = None
                continue
            except Exception as e:
                self._log(f"⚠️  Compose box error: {e}")
                box = None

        if box is None:
            self._log("❌  Could not find compose box.")
            return False

        # Step 2: type the text
        try:
            # Clear box then type
            box.send_keys(Keys.CONTROL + "a")
            box.send_keys(Keys.DELETE)
            time.sleep(0.2)
            box.send_keys(text)
            time.sleep(0.5)
        except Exception as e:
            self._log(f"⚠️  Text input error: {e}")
            return False

        # Step 3: click the send button (most reliable trigger for WA Web)
        send_selectors = [
            'button[data-testid="send"]',
            '[data-testid="compose-btn-send"]',
            'button[aria-label="Send"]',
            'span[data-icon="send"]',
            '#main button[type="submit"]',
            'footer button',
        ]
        for sel in send_selectors:
            try:
                btn = WebDriverWait(self.driver, 4).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                )
                btn.click()
                self._log("📤  Send button clicked.")
                return True
            except (TimeoutException, NoSuchElementException):
                continue
            except Exception as e:
                self._log(f"⚠️  Send button error ({sel}): {e}")

        # Fallback: Enter key if no button found
        try:
            box.send_keys(Keys.ENTER)
            self._log("📤  Sent via Enter key (fallback).")
            return True
        except Exception as e:
            self._log(f"⚠️  Enter fallback error: {e}")

        return False

    def _close_active_chat(self):
        """
        Press Escape to deselect the open chat.
        This forces WA Web to show unread badges for new incoming messages,
        instead of silently marking them as read while the chat is open.
        """
        try:
            body = self.driver.find_element(By.CSS_SELECTOR, "body")
            body.send_keys(Keys.ESCAPE)
            time.sleep(0.3)
        except Exception:
            pass

    # ── Ollama ────────────────────────────────────────────────────────────────

    def _query_ollama(self, user_msg: str) -> str:
        self._log(f"🧠  Querying Ollama ({self.ollama_model})…")
        try:
            resp = requests.post(OLLAMA_API_URL, json={
                "model": self.ollama_model,
                "prompt": user_msg,
                "system": self.system_prompt,
                "stream": False,
            }, timeout=90)
            resp.raise_for_status()
            reply = resp.json().get("response", "").strip()
            self._log(f"🧠  Ollama replied ({len(reply)} chars).")
            return reply
        except requests.exceptions.ConnectionError:
            self._log("❌  Ollama unreachable — run `ollama serve` first.")
            self._status("Ollama offline ⚠")
        except requests.exceptions.Timeout:
            self._log("⏱  Ollama timed out.")
        except Exception as e:
            self._log(f"❌  Ollama error: {e}")
        return ""

    # ── Heartbeat ─────────────────────────────────────────────────────────────

    def _heartbeat(self):
        while not self._stop_event.is_set():
            self._stop_event.wait(HEARTBEAT_SECS)
            if self._stop_event.is_set():
                break
            try:
                if not self.driver:
                    break
                alive = any(self.driver.find_elements(By.CSS_SELECTOR, s)
                            for s in LOADED_INDICATORS)
                self._status("Running ✔" if alive else "Disconnected ⚠")
                if not alive:
                    self._log("💔  Heartbeat: WA Web not found.")
            except WebDriverException:
                self._log("💔  Browser lost.")
                self._status("Browser lost")
                break

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def _cleanup(self):
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
        except Exception:
            pass
        self._log("🔴  Bot stopped.")
        self._status("Stopped")