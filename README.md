# Substack2Markdown (Chrome + Mac fork)

A **Chrome-based, Mac-compatible** fork of Substack2Markdown. This Python tool downloads free and premium Substack posts and saves them as Markdown and HTML, with a simple HTML interface to browse and sort posts. Paid content is saved when you're subscribed to that Substack.

**This fork uses Google Chrome and Selenium’s built-in driver management**, so it works on macOS (Intel and Apple Silicon) without Edge or webdriver_manager.

🆕 [Substack Reader](https://www.substacktools.com/reader) — web version for free Substacks only (by @Firevvork).

## Features

- Converts Substack posts to Markdown (and HTML).
- Generates an HTML author page to browse and sort posts by date or likes.
- Supports **free** and **premium** content (with your subscription).
- **Chrome + Mac**: uses Chrome and Selenium Manager; optional `chromedriver` path for locked-down networks.

## Installation

**Requirements:** Python 3.x, Google Chrome.

```bash
git clone https://github.com/yourusername/Substack2Markdown.git
cd Substack2Markdown

# Optional: virtual environment
# python -m venv venv
# source venv/bin/activate   # Mac/Linux
# .\venv\Scripts\activate   # Windows

pip install -r requirements.txt
```

For the **premium scraper**, set your Substack credentials in `config.py`:

```python
EMAIL = "your-email@example.com"
PASSWORD = "your-password"
```

**Chrome:** Use your normal Chrome install. Selenium will use Selenium Manager to fetch a matching driver. If your network blocks that, install `chromedriver` (e.g. `brew install chromedriver`) and pass `--chrome-driver-path` (see below).

## Usage

### GUI Application (Recommended)

```bash
python substack_gui.py
```

All options are available in the GUI — no command-line knowledge needed. Enter your credentials directly in the Credentials panel; they are passed straight to the browser and also saved to `config.py` for future CLI use.

**Fields:**

| Field | Description |
|-------|-------------|
| Base URL | Scrape all posts from a publication (e.g. `https://author.substack.com`) |
| Single Post URL | Scrape one post by URL — paste from your browser address bar |
| Number of Posts | `0` = all posts; any other number stops after N posts |
| Premium (login) | Opens Chrome to log in before scraping; required for paid posts |
| Headless | Runs Chrome in the background (no visible window); may fail on some Substacks that show a captcha — uncheck if login fails |
| Markdown / HTML dirs | Where to save output files |
| Chrome / ChromeDriver | Optional paths if Selenium Manager can't auto-download the driver |
| User-Agent | Override the browser user agent; can help if you're being blocked |

**Pre-built apps:** See `build_instructions.md` (gitignored, maintainers only) for building a `.dmg` (macOS) or `.exe` (Windows) with PyInstaller.

### Command Line Interface

### Quick start

**Hardcoded config:** Set `BASE_SUBSTACK_URL`, `NUM_POSTS_TO_SCRAPE`, and optionally `USE_PREMIUM` at the top of `substack_scraper.py`, then:

```bash
python substack_scraper.py
```

**Free Substack (no login):**

```bash
python substack_scraper.py --url https://example.substack.com --directory ./substack_md_files
```

**Premium Substack (login in Chrome):**

```bash
python substack_scraper.py --url https://example.substack.com --directory ./substack_md_files --premium
```

---

## Common use cases

### 1. Scrape a **single post** (e.g. from Substack home)

Useful for one article (including paid) from your Substack home or a direct link.

```bash
python substack_scraper.py --premium --single-post "https://substack.com/home/post/p-182828153"
```

Public single post (no login):

```bash
python substack_scraper.py --single-post "https://author.substack.com/p/post-slug"
```

### 2. Limit how many posts to scrape

Scrape only the first N posts (from sitemap/feed order):

```bash
python substack_scraper.py --url https://example.substack.com --number 10
python substack_scraper.py --url https://example.substack.com --premium --number 5
```

### 3. Run premium scraper **headless** (no visible browser)

```bash
python substack_scraper.py --url https://example.substack.com --premium --headless
```

### 4. Custom **markdown** and **HTML** directories

```bash
python substack_scraper.py --url https://example.substack.com \
  --directory ./my_md_posts \
  --html-directory ./my_html_pages
```

### 5. Specify **Chrome** or **ChromeDriver** (Mac / locked-down networks)

Use a specific Chrome binary:

```bash
python substack_scraper.py --url https://example.substack.com --premium \
  --chrome-path "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
```

Use a local `chromedriver` (e.g. from Homebrew):

```bash
# Apple Silicon
python substack_scraper.py --url https://example.substack.com --premium \
  --chrome-driver-path /opt/homebrew/bin/chromedriver

# Intel Mac
python substack_scraper.py --url https://example.substack.com --premium \
  --chrome-driver-path /usr/local/bin/chromedriver
```

Find your chromedriver: `which chromedriver`

### 6. Custom **user agent** (e.g. to help with captcha/blocking)

```bash
python substack_scraper.py --url https://example.substack.com --premium \
  --user-agent "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36..."
```

### 7. Full combination example

Single paid post, headless, custom directories, local chromedriver:

```bash
python substack_scraper.py --premium --headless \
  --single-post "https://substack.com/home/post/p-182828153" \
  --directory ./posts --html-directory ./pages \
  --chrome-driver-path /opt/homebrew/bin/chromedriver
```

### 8. Free Substack, custom dirs, last 20 posts

```bash
python substack_scraper.py --url https://example.substack.com \
  --directory ./substack_md_files --html-directory ./substack_html_pages \
  --number 20
```

---

## All CLI options

| Option | Short | Description |
|--------|-------|-------------|
| `--url` | `-u` | Base Substack URL (e.g. `https://author.substack.com`). |
| `--directory` | `-d` | Directory for Markdown files (default: `substack_md_files`). |
| `--html-directory` | | Directory for HTML files (default: `substack_html_pages`). |
| `--number` | `-n` | Max number of posts to scrape (0 = all). |
| `--premium` | `-p` | Use Chrome + login to scrape paid posts. |
| `--headless` | | Run Chrome headless (premium only). |
| `--single-post` | | Scrape one post by URL (works with `--url` or `--single-post`). |
| `--chrome-path` | | Path to Chrome executable. |
| `--chrome-driver-path` | | Path to `chromedriver` binary. |
| `--user-agent` | | Custom User-Agent string. |

---

## Viewing output

- **HTML:** Open the author page in `substack_html_pages/<writer_name>/` (or your `--html-directory`). Toggle to HTML in the interface to view rendered posts.
- **Markdown:** Use a [Markdown Viewer](https://chromewebstore.google.com/detail/markdown-viewer/ckkdlimhmcjmikdlpkmbgfkaikojcbjk) extension, or the [Substack Reader](https://www.substacktools.com/reader) for free Substacks.

## Troubleshooting

- **Driver/browser mismatch:** Update Chrome, then `pip install -U selenium`. Or install a matching `chromedriver` (e.g. `brew install chromedriver`) and pass `--chrome-driver-path`.
- **Login fails in headless mode:** Substack sometimes blocks headless Chrome with a captcha. Uncheck "Headless" (or drop `--headless`) to run with a visible browser. If that works but headless still doesn't, try passing a realistic `--user-agent`.
- **"Redirected to home instead of the post":** The scraper detected that Substack sent the browser to the inbox instead of the article. This usually means the post requires a subscription the logged-in account doesn't have, or the session hadn't fully settled — try running again.
- **Single post from Substack home:** Use `--single-post` (or the Single Post URL field in the GUI) with the full URL (e.g. `https://substack.com/home/post/p-...`) and enable premium/login if it's a paid post.
- **Post content is empty or wrong:** Make sure you're using the exact URL from your browser address bar, not a shortened or redirect link.

## License

Same as the original project (see LICENSE).
