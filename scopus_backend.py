"""PanScopus Selenium backend for authorized Research4Life and Scopus use.

Single-user Chrome or headless Chromium automation. No credentials/session cookies written to disk.
"""
from __future__ import annotations

import csv
import json
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException, StaleElementReferenceException,
    TimeoutException, WebDriverException,
)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait

LOGIN_URL = "https://login.research4life.org/tacgw/login.cshtml"
GATEWAY = "https://login.research4life.org/tacsgr1portal_research4life_org"
DATABASES_URL = GATEWAY + "/content/databases"
ADVANCED_URL = "https://www.scopus.com/pages/search/publications?type=advanced"
DEFAULT_QUERY = (
    'TITLE-ABS-KEY(("green synthesis" OR "plant-mediated" OR phytogenic) '
    'AND nanoparticle* AND antibiotic* AND (synerg* OR potentiation OR combination) '
    'AND (MDR OR "multidrug resistant" OR MRSA OR ESBL))'
)
MAX_CSV_EXPORT = 20000


def normalize_query(text: str) -> str:
    return re.sub(r"\s+", "", text or "").casefold()


def result_count(text: str) -> int | None:
    found = re.search(r"\b([\d,]+)\s+documents?\s+found\b", text, re.I)
    if found:
        return int(found.group(1).replace(",", ""))
    if re.search(r"\b(?:no|zero)\s+documents?\s+found\b", text, re.I):
        return 0
    return None


def export_count(text: str) -> int | None:
    found = re.search(r"\bExport\s+([\d,]+)\s+documents?\s+to\s+CSV\b", text, re.I)
    return int(found.group(1).replace(",", "")) if found else None


@dataclass(frozen=True)
class SearchResult:
    query: str
    count: int
    results_url: str
    reused: bool = False


@dataclass(frozen=True)
class ExportResult:
    state: str
    expected: int
    rows: int | None = None
    path: str | None = None


class ScopusWorkbench:
    def __init__(self, output_dir: str | Path, logger=print):
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.driver = None
        self.log = logger
        self.last_search: SearchResult | None = None

    def session_alive(self) -> bool:
        try:
            return self.driver is not None and bool(self.driver.window_handles) and bool(self.driver.current_url)
        except WebDriverException:
            return False

    def is_scopus(self) -> bool:
        if not self.session_alive():
            return False
        h = (urlparse(self.driver.current_url).hostname or "").lower()
        return h == "scopus.com" or h.endswith(".scopus.com")

    def _find(self, choices, timeout=20, required=True, enabled=True):
        stop = time.monotonic() + timeout
        while time.monotonic() < stop:
            for by, selector in choices:
                try:
                    for el in self.driver.find_elements(by, selector):
                        if el.is_displayed() and (not enabled or el.is_enabled()):
                            return el
                except (WebDriverException, StaleElementReferenceException):
                    pass
            time.sleep(.3)
        if required:
            raise TimeoutException("Control not found: " + repr(choices))
        return None

    def _click(self, el):
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", el
        )
        try:
            el.click()
        except ElementClickInterceptedException:
            ActionChains(self.driver).move_to_element(el).click().perform()

    def _follow_tab(self, before, timeout=18):
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: bool(set(d.window_handles) - before)
            )
        except TimeoutException:
            return False
        handle = [h for h in self.driver.window_handles if h not in before][-1]
        self.driver.switch_to.window(handle)
        self.log("Active tab: " + self.driver.current_url)
        return True

    def _body(self):
        return self.driver.execute_script(
            "return document.body ? document.body.innerText : '';"
        ) or ""

    def _start_browser(self):
        """Start a separate Chrome/Chromium browser for this user's session.

        Streamlit Community Cloud runs Debian without a desktop display.
        packages.txt installs the matching Chromium and ChromeDriver.
        """
        opts = webdriver.ChromeOptions()
        opts.add_argument("--window-size=1600,1050")
        opts.add_argument("--disable-popup-blocking")
        opts.add_experimental_option("prefs", {
            "download.default_directory": str(self.output_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
        })

        if sys.platform.startswith("linux"):
            opts.add_argument("--headless=new")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--disable-gpu")
            opts.add_argument("--disable-extensions")
            opts.add_argument("--remote-debugging-pipe")
            chromium = (
                shutil.which("chromium")
                or shutil.which("chromium-browser")
                or shutil.which("google-chrome")
                or shutil.which("google-chrome-stable")
            )
            if chromium is None:
                raise RuntimeError(
                    "Chromium is missing from the Cloud container. "
                    "Make sure packages.txt includes 'chromium' and reboot the app."
                )
            opts.binary_location = chromium
            driver_path = shutil.which("chromedriver")
            self.log("Starting headless Chromium on Streamlit Cloud")
        else:
            opts.add_argument("--start-maximized")
            driver_path = None
            self.log("Starting Chrome browser")

        try:
            if driver_path:
                self.driver = webdriver.Chrome(
                    service=Service(executable_path=driver_path),
                    options=opts,
                )
            else:
                self.driver = webdriver.Chrome(options=opts)
        except WebDriverException as exc:
            raise RuntimeError(
                "Chrome could not start. On Streamlit Cloud, verify that "
                "packages.txt installs both chromium and chromium-driver. "
                "Details: " + str(exc)[:600]
            ) from exc

        try:
            self.driver.execute_cdp_cmd(
                "Page.setDownloadBehavior",
                {"behavior": "allow", "downloadPath": str(self.output_dir)},
            )
        except WebDriverException:
            # Chrome's download prefs are used when Page domain is unavailable.
            pass
        self.last_search = None

    def _login(self, username, password):
        self.log("Research4Life Standard Login")
        self.driver.get(LOGIN_URL)
        if "/tacgw/appportal/" in self.driver.current_url.lower():
            return
        standard = self._find([
            (By.XPATH, "//a[contains(.,'Standard Login')]"),
            (By.XPATH, "//button[contains(.,'Standard Login')]"),
        ], timeout=5, required=False)
        if standard:
            old = set(self.driver.window_handles)
            self._click(standard)
            self._follow_tab(old, timeout=5)
        if not username or not password:
            raise ValueError("Research4Life credentials missing in Streamlit secrets")
        user = self._find([
            (By.NAME, "userId"), (By.NAME, "username"), (By.ID, "userId"),
            (By.CSS_SELECTOR, "input[type=email]"), (By.CSS_SELECTOR, "input[type=text]")
        ], timeout=30)
        pwd = self._find([(By.CSS_SELECTOR, "input[type=password]")], timeout=30)
        user.clear()
        user.send_keys(username)
        pwd.clear()
        pwd.send_keys(password)
        submit = self._find([
            (By.CSS_SELECTOR, "button[type=submit]"),
            (By.CSS_SELECTOR, "input[type=submit]"),
            (By.XPATH, "//button[contains(.,'Login')]"),
        ], timeout=5, required=False)
        if submit:
            self._click(submit)
        else:
            pwd.send_keys(Keys.ENTER)
        WebDriverWait(self.driver, 70).until(
            lambda d: "/tacgw/appportal/" in d.current_url.lower()
        )
        self.log("Secure Portal authenticated")

    def _collections(self):
        link = self._find([
            (By.PARTIAL_LINK_TEXT, "Research4Life complete collections"),
            (By.XPATH, "//a[contains(@href,'AppStart.cshtml') and contains(.,'Research4Life')]"),
        ], timeout=30)
        before = set(self.driver.window_handles)
        self._click(link)
        self._follow_tab(before, timeout=40)
        WebDriverWait(self.driver, 60).until(
            lambda d: "/tacsgr1portal_research4life_org" in d.current_url.lower()
        )
        self.log("Authenticated Research4Life gateway open")

    def _open_scopus(self):
        self.driver.get(DATABASES_URL)
        WebDriverWait(self.driver, 45).until(
            lambda d: "/content/databases" in d.current_url.lower()
        )
        letter = self._find([
            (By.XPATH, "//a[normalize-space()='S']"),
            (By.XPATH, "//button[normalize-space()='S']"),
        ], timeout=10, required=False)
        if letter:
            self._click(letter)
        record = self._find([
            (By.XPATH, "//a[contains(@href,'/content/resources/13/193')]"),
            (By.XPATH, "//a[normalize-space()='Scopus']"),
            (By.XPATH, "//a[contains(.,'Scopus')]"),
        ], timeout=35)
        before = set(self.driver.window_handles)
        self._click(record)
        self._follow_tab(before, timeout=20)
        WebDriverWait(self.driver, 90).until(
            lambda d: self.is_scopus() or "/no-access" in d.current_url.lower()
        )
        if not self.is_scopus():
            raise PermissionError("Scopus is unavailable through the authenticated institution")
        self.log("Scopus site reached: " + self.driver.current_url)
        self.log("Checking Advanced Search editor next")

    def connect(self, username="", password=""):
        if not self.session_alive():
            self._start_browser()
        if not self.is_scopus():
            url = self.driver.current_url.lower()
            if "/tacsgr1portal_research4life_org" in url:
                self.log("Reusing authenticated gateway")
            elif "/tacgw/appportal/" in url:
                self._collections()
            else:
                self._login(username, password)
                self._collections()
            self._open_scopus()
        result = self.return_to_advanced()
        self.log("Scopus Advanced Search ready")
        return result

    def _editor(self):
        for root in self.driver.find_elements(By.CSS_SELECTOR, ".monaco-editor"):
            try:
                if root.is_displayed():
                    return root
            except WebDriverException:
                pass
        return None

    def _editor_text(self, root):
        return self.driver.execute_script("""
            const r=arguments[0],n=r.querySelector('.native-edit-context');
            return n?.editContext?.text ||
                [...r.querySelectorAll('.view-line')].map(e=>e.textContent||'').join('');
        """, root)

    def _focus_editor(self, root):
        focused = self.driver.execute_script("""
            const r=arguments[0],e=r.querySelector('.native-edit-context,textarea.inputarea,[role="textbox"]');
            if(e)e.focus();
            return !!e&&r.contains(document.activeElement);
        """, root)
        if not focused:
            lines = root.find_elements(By.CSS_SELECTOR, ".view-line")
            ActionChains(self.driver).move_to_element(lines[0] if lines else root).click().perform()
        if not self.driver.execute_script(
            "return arguments[0].contains(document.activeElement)", root
        ):
            raise RuntimeError("Advanced query editor did not receive focus")

    def _scopus_state(self):
        """Small, non-credential diagnostic for the currently visible Scopus page."""
        if not self.is_scopus():
            return {"url": self.driver.current_url, "title": "Not at Scopus"}
        try:
            state = self.driver.execute_script("""
                const body=document.body?.innerText||'';
                return {
                    url: location.href,
                    title: document.title,
                    ready_state: document.readyState,
                    body_length: body.length,
                    body_excerpt: body.slice(0, 900),
                    monaco_nodes: document.querySelectorAll('.monaco-editor').length,
                    search_links: [...document.querySelectorAll('a,button')]
                        .filter(e => /advanced|search/i.test(
                            e.getAttribute('aria-label') || e.innerText || ''
                        ))
                        .slice(0, 12)
                        .map(e => (e.getAttribute('aria-label') || e.innerText || '')
                            .trim().slice(0, 80))
                };
            """)
            return state if isinstance(state, dict) else {}
        except WebDriverException:
            return {"url": self.driver.current_url, "title": "Unavailable"}

    @staticmethod
    def _page_problem(state):
        sample = (str(state.get("title", "")) + " " +
                  str(state.get("body_excerpt", ""))).lower()
        if any(s in sample for s in (
            "captcha", "verify you are human", "access denied",
            "unusual traffic", "automated requests", "not authorized",
            "please enable javascript", "permission denied",
        )):
            return ("Scopus displayed an access/verification page, not its "
                    "Advanced Search editor. This requires normal authorized "
                    "access resolution; PanScopus will not bypass verification.")
        return None

    def _wait_for_editor(self, timeout=30):
        stop = time.monotonic() + timeout
        while time.monotonic() < stop:
            try:
                if self._editor() is not None:
                    return True
                state = self._scopus_state()
                reason = self._page_problem(state)
                if reason:
                    raise PermissionError(reason)
            except (StaleElementReferenceException, WebDriverException):
                pass
            time.sleep(1)
        return False

    def _click_advanced_link(self):
        """Follow Scopus's visible Advanced Search control when deep links fail."""
        candidates = [
            (By.XPATH, "//a[contains(translate(normalize-space(.),"
             "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),"
             "'advanced search')]"),
            (By.XPATH, "//button[contains(translate(normalize-space(.),"
             "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),"
             "'advanced search')]"),
            (By.XPATH, "//*[@role='link' and contains("
             "translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ',"
             "'abcdefghijklmnopqrstuvwxyz'),'advanced')]"),
            (By.XPATH, "//*[@role='button' and contains("
             "translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ',"
             "'abcdefghijklmnopqrstuvwxyz'),'advanced')]"),
        ]
        element = self._find(candidates, timeout=4, required=False)
        if element is None:
            return False
        before = set(self.driver.window_handles)
        self._click(element)
        self._follow_tab(before, timeout=3)
        return True

    def return_to_advanced(self):
        if not self.is_scopus():
            raise RuntimeError("Connect to Scopus first")

        if self._editor() is not None:
            self.log("Advanced Search editor already ready")
            return self.driver.current_url

        self.log("Opening Scopus Advanced Search")
        if "type=advanced" not in self.driver.current_url.lower():
            self.driver.get(ADVANCED_URL)

        if self._wait_for_editor(32):
            self.log("Advanced Search editor loaded")
            return self.driver.current_url

        first = self._scopus_state()
        self.log(
            "Advanced editor not found after direct navigation. "
            "URL=" + str(first.get("url", "")) +
            "; page=" + str(first.get("title", ""))
        )

        # Some Scopus sessions create a client-side navigation state
        # only after visiting the Search page from the site menu.
        # This uses ordinary first-party navigation, not a bypass.
        self.log("Trying Scopus Search page and its Advanced Search link")
        for url in (
            "https://www.scopus.com/pages/home#basic",
            "https://www.scopus.com/pages/search/publications?type=basic",
        ):
            self.driver.get(url)
            self.log("Scopus navigation: " + self.driver.current_url)
            if self._wait_for_editor(10):
                self.log("Advanced Search editor loaded")
                return self.driver.current_url
            if self._click_advanced_link() and self._wait_for_editor(20):
                self.log("Advanced Search editor loaded through site link")
                return self.driver.current_url

        final = self._scopus_state()
        self.log(
            "Advanced Search unresolved. URL=" + str(final.get("url", "")) +
            "; title=" + str(final.get("title", "")) +
            "; DOM ready=" + str(final.get("ready_state", "")) +
            "; Monaco nodes=" + str(final.get("monaco_nodes", 0))
        )
        raise RuntimeError(
            self._page_problem(final)
            or "Scopus Advanced Search editor did not load in Cloud Chromium. "
               "Check the diagnostic screenshot and page-state JSON below; "
               "the Research4Life login succeeded, but the editor is not yet accessible."
        )

    def _results_match(self, query):
        return (
            "searchid=" in self.driver.current_url.lower()
            and "advanced query" in self._body().lower()
            and normalize_query(query) in normalize_query(self._body())
        )

    def _count(self, timeout=60):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            total = result_count(self._body())
            if total is not None:
                return total
            time.sleep(.8)
        raise RuntimeError("Scopus did not display a verifiable result count")

    def _fill(self, root, query):
        self._focus_editor(root)
        ActionChains(self.driver).key_down(Keys.CONTROL).send_keys("a").key_up(
            Keys.CONTROL
        ).send_keys(Keys.BACKSPACE).perform()
        try:
            self.driver.execute_cdp_cmd("Input.insertText", {"text": query})
        except WebDriverException:
            ActionChains(self.driver).send_keys(query).perform()
        if normalize_query(self._editor_text(root)) != normalize_query(query):
            self._focus_editor(root)
            ActionChains(self.driver).key_down(Keys.CONTROL).send_keys("a").key_up(
                Keys.CONTROL
            ).send_keys(Keys.BACKSPACE).send_keys(query).perform()
        WebDriverWait(self.driver, 12).until(
            lambda d: normalize_query(self._editor_text(root)) == normalize_query(query)
        )
        self.log("Exact query verified in editor")

    def search(self, query):
        query = (query or "").strip()
        if not query:
            raise ValueError("Enter a Scopus advanced query")
        if not self.is_scopus():
            raise RuntimeError("Connect to Scopus first")
        reused = self._results_match(query)
        if not reused:
            self.return_to_advanced()
            root = self._editor()
            self._fill(root, query)
            buttons = [
                b for b in self.driver.find_elements(
                    By.XPATH, "//button[normalize-space()='Search' or .//span[normalize-space()='Search']]"
                ) if b.is_displayed() and b.is_enabled()
            ]
            if not buttons:
                raise RuntimeError("Scopus Search button missing")
            rect = root.rect
            buttons.sort(
                key=lambda b: abs(b.rect["y"]-rect["y"]-rect["height"])
                + abs(b.rect["x"]-rect["x"])/4
            )
            self._click(buttons[0])
            WebDriverWait(self.driver, 90).until(
                lambda d: "searchid=" in d.current_url.lower()
            )
            WebDriverWait(self.driver, 65).until(lambda d: self._results_match(query))
        total = self._count()
        result = SearchResult(query, total, self.driver.current_url, reused)
        self.last_search = result
        self.log(f"Verified search: {total:,} documents")
        return result

    def _dialog_total(self):
        return export_count(self._body())

    def _dialog(self):
        return self.driver.execute_script(r"""
            const vis=e=>{
                const r=e.getBoundingClientRect(),s=getComputedStyle(e);
                return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none';
            };
            const contains=e=>{
                const t=(e.innerText||'').toLowerCase();
                return t.includes('what information do you want to export') &&
                    /export\s+[\d,]+\s+documents?\s+to\s+csv/i.test(t);
            };
            let nodes=[...document.querySelectorAll('[role="dialog"],dialog,[aria-modal="true"]')];
            let modal=nodes.find(e=>vis(e)&&contains(e));
            if(modal)return modal;
            const headings=[...document.querySelectorAll('h1,h2,h3,h4,div,span')]
                .filter(e=>vis(e)&&/^Export\s+[\d,]+\s+documents?\s+to\s+CSV$/i.test((e.innerText||'').trim()));
            headings.sort((a,b)=>(a.innerText||'').length-(b.innerText||'').length);
            for(const h of headings){
                for(let p=h.parentElement;p&&p!==document.body;p=p.parentElement){
                    if(contains(p)&&(p.innerText||'').includes('Select all information'))return p;
                }
            }
            return contains(document.body)?document.body:null;
        """)

    def _csv_option(self):
        return self.driver.execute_script("""
            const nodes=[...document.querySelectorAll('a,button,span,li,div,[role="menuitem"],[role="option"]')];
            const arr=nodes.filter(e=>{
                const r=e.getBoundingClientRect();
                return r.width>0&&r.height>0&&(e.innerText||'').trim()==='CSV';
            });
            arr.sort((a,b)=>a.getBoundingClientRect().width*a.getBoundingClientRect().height-
                b.getBoundingClientRect().width*b.getBoundingClientRect().height);
            return arr[0]||null;
        """)

    def _select_all_results(self):
        check = self._find([
            (By.ID, "selectAllCheck"),
            (By.CSS_SELECTOR, "label[for='selectAllCheck']"),
            (By.XPATH, "//*[@role='checkbox' and contains(@aria-label,'All')]"),
        ], timeout=6, required=False)
        if check is not None:
            status = self.driver.execute_script("""
                const e=arguments[0],c=e.matches('label')&&e.htmlFor?
                    document.getElementById(e.htmlFor):e;
                if(!c)return null;
                if(c.matches('input[type="checkbox"]'))return c.checked;
                const v=c.getAttribute('aria-checked');
                return v==='true'?true:(v==='false'?false:null);
            """, check)
            if status is False:
                self._click(check)

    def _open_csv(self):
        if self._dialog_total() is not None:
            self.log("Existing CSV dialog preserved")
            return
        self._select_all_results()
        item = self._csv_option()
        if item is None:
            export = self._find([
                (By.ID, "exportBtn"), (By.ID, "export_Menu"),
                (By.XPATH, "//button[normalize-space()='Export']"),
                (By.XPATH, "//*[@role='button' and normalize-space()='Export']"),
                (By.XPATH, "//a[normalize-space()='Export']"),
            ], timeout=20)
            self._click(export)
            WebDriverWait(self.driver, 15).until(
                lambda d: self._csv_option() is not None or self._dialog_total() is not None
            )
            item = self._csv_option()
        if self._dialog_total() is None and item is not None:
            self._click(item)
        WebDriverWait(self.driver, 25).until(lambda d: self._dialog_total() is not None)
        self.log(f"CSV dialog targets {self._dialog_total()} documents")

    def _set_csv_range(self, total):
        modal = self._dialog()
        if modal is None:
            raise RuntimeError("CSV export modal missing")
        choice = self.driver.execute_script(r"""
            const root=arguments[0],vis=e=>{
                const r=e.getBoundingClientRect();
                return r.width>0&&r.height>0;
            };
            const labels=[...root.querySelectorAll('label,[role="radio"],button,span,div')]
                .filter(vis).filter(e=>(e.innerText||e.getAttribute('aria-label')||'').trim()==='Documents');
            const title=[...root.querySelectorAll('*')]
                .find(e=>vis(e)&&(e.innerText||'').trim()==='What information do you want to export?');
            const boundary=title?title.getBoundingClientRect().top:Infinity;
            labels.sort((a,b)=>{
                const x=a.getBoundingClientRect(),y=b.getBoundingClientRect();
                return x.width*x.height-y.width*y.height;
            });
            const el=labels.find(e=>e.getBoundingClientRect().top<boundary);
            return el?(el.closest('label,[role="radio"],button')||el):null;
        """, modal)
        if choice is None:
            raise RuntimeError("Document range selector not found in the CSV modal")
        self._click(choice)
        stop = time.monotonic() + 15
        field = None
        while time.monotonic() < stop:
            modal = self._dialog()
            if modal is None:
                break
            field = self.driver.execute_script(r"""
                const root=arguments[0],vis=e=>{
                    const r=e.getBoundingClientRect();
                    return r.width>10&&r.height>10;
                };
                const opts=[...root.querySelectorAll('input')]
                    .filter(vis).filter(e=>!['hidden','checkbox','radio'].includes((e.type||'').toLowerCase()));
                const desc=e=>[
                    e.getAttribute('aria-label')||'',
                    e.getAttribute('placeholder')||'',e.name||'',e.id||''
                ].join(' ').toLowerCase();
                let to=opts.find(e=>/\bto\b|range.*end/.test(desc(e)));
                if(to)return to;
                const marker=[...root.querySelectorAll('*')]
                    .find(e=>vis(e)&&(e.innerText||'').trim()==='What information do you want to export?');
                const top=marker?marker.getBoundingClientRect().top:Infinity;
                const before=opts.filter(e=>e.getBoundingClientRect().top<top);
                before.sort((a,b)=>a.getBoundingClientRect().left-b.getBoundingClientRect().left);
                return before.length?before[before.length-1]:null;
            """, modal)
            if field is not None and field.is_enabled():
                break
            time.sleep(.4)
        if field is None or not field.is_enabled():
            raise RuntimeError("CSV range 'To' field missing or disabled")
        self._click(field)
        field.send_keys(Keys.CONTROL, "a")
        field.send_keys(str(total), Keys.TAB)
        if (field.get_attribute("value") or "").replace(",", "") != str(total):
            raise RuntimeError("CSV range To value not accepted")
        try:
            WebDriverWait(self.driver, 12).until(lambda d: self._dialog_total() == total)
        except TimeoutException as exc:
            raise RuntimeError(
                f"CSV dialog remains at {self._dialog_total()} of {total}; partial export blocked"
            ) from exc
        self.log(f"Full CSV range verified: 1–{total}")

    def _metadata(self):
        modal = self._dialog()
        if modal is None:
            raise RuntimeError("Missing CSV metadata modal")
        def status(root):
            return self.driver.execute_script("""
                const els=[...arguments[0].querySelectorAll('input[type="checkbox"],[role="checkbox"]')];
                const checked=els.filter(e=>e.matches('input')?e.checked:
                    e.getAttribute('aria-checked')==='true'||e.getAttribute('data-state')==='checked');
                return [els.length,checked.length];
            """, root)
        total, checked = status(modal)
        button = self.driver.execute_script("""
            const root=arguments[0];
            const els=[...root.querySelectorAll('a,button,label,[role="button"],span,div')]
                .filter(e=>{
                    const r=e.getBoundingClientRect();
                    return r.width>0&&r.height>0&&(e.innerText||'').trim()==='Select all information';
                });
            els.sort((a,b)=>a.getBoundingClientRect().width*a.getBoundingClientRect().height-
                b.getBoundingClientRect().width*b.getBoundingClientRect().height);
            return els[0]?(els[0].closest('a,button,label,[role="button"]')||els[0]):null;
        """, modal)
        if button is None:
            raise RuntimeError("Metadata 'Select all information' control missing")
        if checked < max(5,total-1):
            self._click(button)
        time.sleep(.45)
        _, new_checked = status(self._dialog())
        if new_checked < 5 or new_checked < checked:
            raise RuntimeError("Scopus did not accept metadata selection")
        self.log(f"CSV metadata checked: {new_checked}/{total}")

    def _submit_csv(self):
        modal = self._dialog()
        if modal is None:
            raise RuntimeError("CSV dialog closed unexpectedly")
        buttons = [
            el for el in modal.find_elements(
                By.XPATH, ".//button[normalize-space()='Export' or .//span[normalize-space()='Export']]"
            ) if el.is_displayed() and el.is_enabled() and el.get_attribute('aria-disabled') != 'true'
        ]
        if not buttons:
            raise RuntimeError("Final CSV Export button is unavailable")
        buttons.sort(key=lambda e:e.rect["y"], reverse=True)
        self._click(buttons[0])
        self.log("Final CSV Export clicked")

    def _log_export(self, result, search):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.output_dir / f"scopus_export_{stamp}.json"
        path.write_text(json.dumps({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "query":search.query, "results_url":search.results_url,
            "total_results":search.count, "downloaded_rows":result.rows,
            "status":result.state, "file":result.path,
        }, indent=2), encoding="utf-8")
        self.log("Export provenance: " + str(path))

    def export_csv(self, timeout=180):
        search = self.last_search
        if search is None:
            raise RuntimeError("Run a search before exporting")
        if not self.is_scopus() or not self._results_match(search.query):
            raise RuntimeError("Scopus result query changed; export blocked")
        total = self._count(timeout=35)
        if total != search.count:
            raise RuntimeError("Scopus result count changed; run Search again")
        if not 0 < total <= MAX_CSV_EXPORT:
            raise RuntimeError("No results, or result count exceeds single CSV export limit")
        before = {p.name for p in self.output_dir.iterdir() if p.is_file()}
        self._open_csv()
        if self._dialog_total() != total:
            self._set_csv_range(total)
        if self._dialog_total() != total:
            raise RuntimeError(f"CSV selection {self._dialog_total()} != {total}. Export blocked.")
        self._metadata()
        self._submit_csv()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            files = [
                p for p in self.output_dir.iterdir()
                if p.is_file() and p.name not in before
                and p.suffix.lower() == ".csv" and p.stat().st_size > 0
            ]
            if files and not list(self.output_dir.glob("*.crdownload")):
                path = max(files, key=lambda p:p.stat().st_mtime)
                with path.open(encoding="utf-8-sig", errors="replace", newline="") as handle:
                    rows = sum(1 for _ in csv.DictReader(handle))
                result = ExportResult(
                    "complete" if rows == total else "partial_or_mismatch",
                    total, rows, str(path)
                )
                self._log_export(result, search)
                self.log(f"CSV downloaded: {rows}/{total} rows")
                return result
            time.sleep(2)
        result = ExportResult("pending", total)
        self._log_export(result, search)
        self.log("CSV not downloaded yet; check Scopus Exports Dashboard")
        return result

    def save_debug(self, label="error"):
        if not self.is_scopus():
            return None
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        png = self.output_dir / f"scopus_{label}_{stamp}.png"
        details = self.output_dir / f"scopus_{label}_{stamp}.json"
        self.driver.save_screenshot(str(png))
        state = self._scopus_state()
        state.update({
            "diagnostic_timestamp": stamp,
            "expected_advanced_url": ADVANCED_URL,
            "visible_editor": self._editor() is not None,
            "dialog_count": self._dialog_total(),
        })
        details.write_text(
            json.dumps(state, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return str(png), str(details)

    def close(self):
        if self.session_alive():
            self.driver.quit()
        self.driver = None
        self.last_search = None
