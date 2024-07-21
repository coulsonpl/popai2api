from app import create_app
from app.config import get_env_value
import time
import schedule
from app.token import token_manager_thread

app = create_app()

if __name__ == '__main__':
    port = int(get_env_value('SERVER_PORT', 3000))
     # 启动 Token 管理器线程
    token_manager_thread.start()
    
    try:
        app.run(host='0.0.0.0', port=port)
    finally:
        # 确保在应用关闭时停止 Token 管理器线程
        token_manager_thread.stop()
        token_manager_thread.join()
