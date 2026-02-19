#!/usr/bin/env python3
"""
Substack2Markdown GUI Application
A graphical interface for the Substack scraper tool.
"""

import importlib
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import sys
import os
from pathlib import Path
from urllib.parse import urlparse

import config
from substack_scraper import (
    PremiumSubstackScraper,
    SubstackScraper,
    BASE_MD_DIR,
    BASE_HTML_DIR,
    BASE_SUBSTACK_URL,
    NUM_POSTS_TO_SCRAPE,
    USE_PREMIUM
)

try:
    from config import EMAIL, PASSWORD
except ImportError:
    config_path = Path(__file__).parent / "config.py"
    if not config_path.exists():
        with open(config_path, 'w') as f:
            f.write('EMAIL = ""\n')
            f.write('PASSWORD = ""\n')
    from config import EMAIL, PASSWORD


class SubstackScraperGUI:
    BG = "#ffffff"
    FG = "#1a1a1a"
    ENTRY_BG = "#ffffff"
    OUTPUT_BG = "#ffffff"
    OUTPUT_FG = "#1a1a1a"
    ACCENT = "#2563eb"

    def __init__(self, root):
        self.root = root
        self.root.title("Substack2Markdown")
        self.root.configure(bg=self.BG)

        self.scraping = False
        self.scraper_thread = None

        self.setup_light_theme()
        self.create_widgets()

        self.root.update_idletasks()
        self.root.minsize(720, 420)
        self.root.geometry("")  # Let window shrink to natural size
        self.root.update_idletasks()

    def setup_light_theme(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")  # consistent light look and color control
        except tk.TclError:
            style.theme_use("default")
        style.configure(".", background=self.BG, foreground=self.FG)
        style.configure("TFrame", background=self.BG)
        style.configure("TLabel", background=self.BG, foreground=self.FG)
        style.configure("TLabelframe", background=self.BG)
        style.configure("TLabelframe.Label", background=self.BG, foreground=self.FG)
        style.configure("TEntry", fieldbackground=self.ENTRY_BG, foreground=self.FG, insertcolor=self.FG)
        style.configure("TButton", background="#f0f0f0", foreground=self.FG)
        style.configure("TCheckbutton", background=self.BG, foreground=self.FG)
        style.map("TButton", background=[("active", "#e0e0e0")])
        style.map("TCheckbutton", background=[("active", self.BG)])

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        row = 0

        title_label = ttk.Label(main_frame, text="Substack2Markdown", font=("Arial", 16, "bold"))
        title_label.grid(row=row, column=0, columnspan=2, pady=(0, 12))
        row += 1

        url_frame = ttk.LabelFrame(main_frame, text="Substack URL", padding="8")
        url_frame.grid(row=row, column=0, sticky=(tk.W, tk.E, tk.N), pady=4, padx=(0, 4))
        url_frame.columnconfigure(1, weight=1)

        ttk.Label(url_frame, text="Base URL:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.url_var = tk.StringVar(value="")
        ttk.Entry(url_frame, textvariable=self.url_var, width=36).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        ttk.Label(url_frame, text="Single Post URL:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=(6, 0))
        self.single_post_var = tk.StringVar(value="")
        ttk.Entry(url_frame, textvariable=self.single_post_var, width=36).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5, pady=(6, 0))
        ttk.Label(url_frame, text="(one or the other)", font=("Arial", 8)).grid(row=2, column=1, sticky=tk.W, padx=5)

        options_frame = ttk.LabelFrame(main_frame, text="Options", padding="8")
        options_frame.grid(row=row, column=1, sticky=(tk.W, tk.E, tk.N), pady=4, padx=(4, 0))
        options_frame.columnconfigure(1, weight=1)
        ttk.Label(options_frame, text="Number of Posts:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.number_var = tk.StringVar(value="0")
        ttk.Entry(options_frame, textvariable=self.number_var, width=8).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Label(options_frame, text="(0 = all)").grid(row=0, column=2, sticky=tk.W, padx=2)
        self.premium_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Premium (login)", variable=self.premium_var).grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=5, pady=4)
        self.headless_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Headless (run in background)", variable=self.headless_var).grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5)
        row += 1

        dir_frame = ttk.LabelFrame(main_frame, text="Directories", padding="8")
        dir_frame.grid(row=row, column=0, sticky=(tk.W, tk.E, tk.N), pady=4, padx=(0, 4))
        dir_frame.columnconfigure(1, weight=1)
        ttk.Label(dir_frame, text="Markdown:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.md_dir_var = tk.StringVar(value=BASE_MD_DIR)
        ttk.Entry(dir_frame, textvariable=self.md_dir_var, width=28).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        ttk.Button(dir_frame, text="Browse", command=self.browse_md_dir).grid(row=0, column=2, padx=5)
        ttk.Label(dir_frame, text="HTML:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=(6, 0))
        self.html_dir_var = tk.StringVar(value=BASE_HTML_DIR)
        ttk.Entry(dir_frame, textvariable=self.html_dir_var, width=28).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5, pady=(6, 0))
        ttk.Button(dir_frame, text="Browse", command=self.browse_html_dir).grid(row=1, column=2, padx=5, pady=(6, 0))

        cred_frame = ttk.LabelFrame(main_frame, text="Credentials (Premium)", padding="8")
        cred_frame.grid(row=row, column=1, sticky=(tk.W, tk.E, tk.N), pady=4, padx=(4, 0))
        cred_frame.columnconfigure(1, weight=1)
        ttk.Label(cred_frame, text="Email:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.email_var = tk.StringVar(value=EMAIL)
        ttk.Entry(cred_frame, textvariable=self.email_var, width=28).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        ttk.Label(cred_frame, text="Password:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=(6, 0))
        self.password_var = tk.StringVar(value=PASSWORD)
        ttk.Entry(cred_frame, textvariable=self.password_var, show="*", width=28).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5, pady=(6, 0))
        row += 1

        advanced_frame = ttk.LabelFrame(main_frame, text="Advanced (Optional)", padding="8")
        advanced_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=4)
        advanced_frame.columnconfigure(1, weight=1)
        advanced_frame.columnconfigure(3, weight=1)
        advanced_frame.columnconfigure(5, weight=1)
        ttk.Label(advanced_frame, text="Chrome:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.chrome_path_var = tk.StringVar(value="")
        ttk.Entry(advanced_frame, textvariable=self.chrome_path_var, width=22).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        ttk.Button(advanced_frame, text="Browse", command=self.browse_chrome_path).grid(row=0, column=2, padx=5)
        ttk.Label(advanced_frame, text="ChromeDriver:").grid(row=0, column=3, sticky=tk.W, padx=(15, 5))
        self.chrome_driver_var = tk.StringVar(value="")
        ttk.Entry(advanced_frame, textvariable=self.chrome_driver_var, width=22).grid(row=0, column=4, sticky=(tk.W, tk.E), padx=5)
        ttk.Button(advanced_frame, text="Browse", command=self.browse_chrome_driver).grid(row=0, column=5, padx=5)
        ttk.Label(advanced_frame, text="User-Agent:").grid(row=0, column=6, sticky=tk.W, padx=(15, 5))
        self.user_agent_var = tk.StringVar(value="")
        ttk.Entry(advanced_frame, textvariable=self.user_agent_var, width=24).grid(row=0, column=7, sticky=(tk.W, tk.E), padx=5)
        row += 1

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2, pady=12)
        self.start_button = ttk.Button(button_frame, text="Start Scraping", command=self.start_scraping)
        self.start_button.pack(side=tk.LEFT, padx=5)
        self.stop_button = ttk.Button(button_frame, text="Stop", command=self.stop_scraping, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        row += 1

        output_frame = ttk.LabelFrame(main_frame, text="Output", padding="10")
        output_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(row, weight=1)

        self.output_text = scrolledtext.ScrolledText(
            output_frame, height=8, width=70, wrap=tk.WORD,
            bg=self.OUTPUT_BG, fg=self.OUTPUT_FG, insertbackground=self.FG,
            font=("Menlo", 10) if sys.platform == "darwin" else ("Consolas", 10)
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)

        self.redirect_output()

    def browse_md_dir(self):
        directory = filedialog.askdirectory(title="Select Markdown Directory", initialdir=self.md_dir_var.get())
        if directory:
            self.md_dir_var.set(directory)

    def browse_html_dir(self):
        directory = filedialog.askdirectory(title="Select HTML Directory", initialdir=self.html_dir_var.get())
        if directory:
            self.html_dir_var.set(directory)

    def browse_chrome_path(self):
        if sys.platform == "darwin":
            file_path = filedialog.askopenfilename(
                title="Select Chrome Executable",
                initialdir="/Applications",
                filetypes=[("Application", "*.app"), ("All files", "*.*")]
            )
            if file_path and file_path.endswith(".app"):
                file_path = os.path.join(file_path, "Contents/MacOS/Google Chrome")
        else:
            file_path = filedialog.askopenfilename(
                title="Select Chrome Executable",
                filetypes=[("Executable", "*.exe"), ("All files", "*.*")]
            )
        if file_path:
            self.chrome_path_var.set(file_path)

    def browse_chrome_driver(self):
        file_path = filedialog.askopenfilename(
            title="Select ChromeDriver",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")]
        )
        if file_path:
            self.chrome_driver_var.set(file_path)

    def redirect_output(self):
        class TextRedirector:
            def __init__(self, text_widget):
                self.text_widget = text_widget

            def write(self, string):
                self.text_widget.insert(tk.END, string)
                self.text_widget.see(tk.END)
                self.text_widget.update()

            def flush(self):
                pass

        sys.stdout = TextRedirector(self.output_text)
        sys.stderr = TextRedirector(self.output_text)

    def log(self, message):
        self.output_text.insert(tk.END, f"{message}\n")
        self.output_text.see(tk.END)
        self.root.update()

    def validate_inputs(self):
        url = self.url_var.get().strip()
        single_post = self.single_post_var.get().strip()

        if not url and not single_post:
            messagebox.showerror("Error", "Please provide either a Substack URL or a Single Post URL")
            return False

        if url and single_post:
            messagebox.showerror("Error", "Please provide either a Substack URL OR a Single Post URL, not both")
            return False

        if self.premium_var.get():
            email = self.email_var.get().strip()
            password = self.password_var.get().strip()
            if not email or not password:
                messagebox.showerror("Error", "Email and password are required for premium scraping")
                return False

        try:
            number = int(self.number_var.get())
            if number < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Number of posts must be a non-negative integer")
            return False

        return True

    def start_scraping(self):
        if not self.validate_inputs():
            return

        self.scraping = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)

        self.output_text.delete(1.0, tk.END)

        self.scraper_thread = threading.Thread(target=self.run_scraper, daemon=True)
        self.scraper_thread.start()

    def stop_scraping(self):
        self.scraping = False
        self.log("\n[Stopping scraper...]")
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)

    def run_scraper(self):
        try:
            if self.premium_var.get():
                self.update_config()

            url = self.url_var.get().strip()
            single_post = self.single_post_var.get().strip()
            md_dir = self.md_dir_var.get().strip() or BASE_MD_DIR
            html_dir = self.html_dir_var.get().strip() or BASE_HTML_DIR
            number = int(self.number_var.get()) if self.number_var.get() else 0
            premium = self.premium_var.get()
            headless = self.headless_var.get()
            chrome_path = self.chrome_path_var.get().strip() or ''
            chrome_driver_path = self.chrome_driver_var.get().strip() or ''
            user_agent = self.user_agent_var.get().strip() or ''

            self.log("=" * 60)
            self.log("Starting Substack Scraper")
            self.log("=" * 60)

            if single_post:
                self.log(f"Single Post Mode: {single_post}")
                parsed = urlparse(single_post)
                if "/home/post/" in single_post or parsed.netloc == "substack.com":
                    base_url = "https://substack.com/"
                else:
                    base_url = f"{parsed.scheme}://{parsed.netloc}/"

                if premium:
                    scraper = PremiumSubstackScraper(
                        base_url,
                        md_save_dir=md_dir,
                        html_save_dir=html_dir,
                        headless=headless,
                        chrome_path=chrome_path,
                        chrome_driver_path=chrome_driver_path,
                        user_agent=user_agent,
                        skip_url_fetch=True,
                        email=self.email_var.get().strip(),
                        password=self.password_var.get().strip()
                    )
                    scraper.scrape_single_post(single_post)
                else:
                    scraper = SubstackScraper(
                        base_url,
                        md_save_dir=md_dir,
                        html_save_dir=html_dir,
                        skip_url_fetch=True
                    )
                    scraper.scrape_single_post(single_post)
            else:
                self.log(f"Base URL: {url}")
                self.log(f"Number of posts: {number if number > 0 else 'All'}")

                if premium:
                    scraper = PremiumSubstackScraper(
                        url,
                        md_save_dir=md_dir,
                        html_save_dir=html_dir,
                        headless=headless,
                        chrome_path=chrome_path,
                        chrome_driver_path=chrome_driver_path,
                        user_agent=user_agent,
                        email=self.email_var.get().strip(),
                        password=self.password_var.get().strip()
                    )
                    scraper.scrape_posts(number)
                else:
                    scraper = SubstackScraper(
                        url,
                        md_save_dir=md_dir,
                        html_save_dir=html_dir
                    )
                    scraper.scrape_posts(number)

            self.log("\n" + "=" * 60)
            self.log("Scraping completed successfully!")
            self.log("=" * 60)
            messagebox.showinfo("Success", "Scraping completed successfully!")

        except Exception as e:
            error_msg = f"Error during scraping: {str(e)}"
            self.log(f"\nERROR: {error_msg}")
            messagebox.showerror("Error", error_msg)
        finally:
            self.scraping = False
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)

    def update_config(self):
        try:
            config_path = Path(__file__).parent / "config.py"
            email = self.email_var.get().strip()
            password = self.password_var.get().strip()

            with open(config_path, 'w') as f:
                f.write(f'EMAIL = "{email}"\n')
                f.write(f'PASSWORD = "{password}"\n')

            importlib.reload(config)

        except Exception as e:
            self.log(f"Warning: Could not update config.py: {e}")


def main():
    root = tk.Tk()
    app = SubstackScraperGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
