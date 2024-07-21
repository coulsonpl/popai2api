import time
import threading
import schedule
import undetected_chromedriver as uc
from pyvirtualdisplay import Display
import logging
from collections import deque
from datetime import datetime, timedelta
from app.config import POPAI_BASE_URL, get_env_value
from app.config import proxy_pool

class Token:
    def __init__(self, value):
        self.value = value
        self.created_at = datetime.now()
        self.use_count = 0

    def is_valid(self):
        return self.use_count <= 3 and (datetime.now() - self.created_at) < timedelta(hours=1)

    def get_lifetime(self):
        return datetime.now() - self.created_at

class TokenManager:
    def __init__(self, min_valid_tokens=50):
        self.tokens = deque()
        self.min_valid_tokens = min_valid_tokens

    def add_token(self, token_value):
        self.tokens.append(Token(token_value))

    def get_token(self):
        while self.tokens and not self.tokens[0].is_valid():
            self.tokens.popleft()
        
        if not self.tokens:
            return None
        
        token = self.tokens[0]
        token.use_count += 1
        return token.value

    def count_valid_tokens(self):
        return sum(1 for token in self.tokens if token.is_valid())

    def remove_invalid_tokens(self):
        invalid_tokens = [token for token in self.tokens if not token.is_valid()]
        for token in invalid_tokens:
            lifetime = token.get_lifetime()
            print(f"Removing token: value = {token.value}, use count = {token.use_count}, "
                  f"lifetime = {lifetime.total_seconds():.2f} seconds")
        
        self.tokens = deque(token for token in self.tokens if token.is_valid())

    def remove_token(self, token_value):
        original_length = len(self.tokens)
        self.tokens = deque(token for token in self.tokens if token.value != token_value)
        removed = len(self.tokens) < original_length
        if removed:
            print(f"one token has been removed.")
        else:
            print(f"Token with value {token_value} was not found.")
        return removed

class TokenManagerThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.token_manager = TokenManager()
        self.driver = None
        self.display = None
        self.running = True

    def run(self):
        # 启动后立即获取一次 gtoken
        self.immediate_job()

        def scheduled_job():
            self.immediate_job()

        schedule.every(10).seconds.do(scheduled_job)

        while self.running:
            schedule.run_pending()
            time.sleep(1)

    def immediate_job(self):
        self.token_manager.remove_invalid_tokens()
        valid_tokens = self.token_manager.count_valid_tokens()
        
        if valid_tokens < self.token_manager.min_valid_tokens:
            if self.driver is None:
                self.driver, self.display = self.setup_browser()
            gtoken = self.get_gtoken(self.driver)
            if gtoken:
                self.token_manager.add_token(gtoken)
            else:
                print("Failed to get token. Closing current window.")
                self.close_browser()
        
        print(f"Current valid token count: {valid_tokens}")
        
        if valid_tokens >= self.token_manager.min_valid_tokens:
            print("Valid token count is sufficient, closing browser to save memory")
            self.close_browser()

    def setup_browser(self):
        display = Display(visible=0, size=(1280, 720), backend="xvfb")
        display.start()

        options = uc.ChromeOptions()
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        proxies = proxy_pool.get_random_proxy()
        if 'https' in proxies and '@' not in proxies['https']:
            options.add_argument(f"--proxy-server={proxies['https']}")

        driver = uc.Chrome(options=options)
        driver.get(POPAI_BASE_URL)
        return driver, display

    def get_gtoken(self, driver):
        try:
            with open('./recaptcha__zh_cn.js', 'r', encoding='utf-8', errors='ignore') as f:
                str_js = f.read()

            gtoken = driver.execute_async_script(str_js)
            # print(f"Got new GToken: {gtoken}")
            return gtoken
        except Exception as e:
            logging.error(f"An error occurred while getting GToken: {e}")
            return None

    def close_browser(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
        if self.display:
            self.display.stop()
            self.display = None

    def stop(self):
        self.running = False
        self.close_browser()

    def get_token(self):
        return self.token_manager.get_token()

    def remove_token(self, token_value):
        return self.token_manager.remove_token(token_value)

token_manager_thread = TokenManagerThread()