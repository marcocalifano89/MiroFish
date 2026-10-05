"""\n配置管理\n统一从项目根目录的 .env 文件加载配置\n"""

import os
import shutil
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
# 路径: MiroFish/.env (相对于 backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # 如果根目录没有 .env，尝试加载环境变量（用于生产环境）
    load_dotenv(override=True)


class Config:
    """Flask配置类"""
    
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # JSON配置 - 禁用ASCII转义，让中文直接显示
    JSON_AS_ASCII = False
    
    # LLM providers. Subscription modes use the provider's supported CLI login
    # through a loopback-only OpenAI-compatible bridge; no account token is read.
    LLM_PROVIDER = os.environ.get('LLM_PROVIDER', 'api').strip().lower()
    SUBSCRIPTION_PROVIDERS = {'codex_subscription', 'claude_subscription'}
    _is_subscription_provider = LLM_PROVIDER in SUBSCRIPTION_PROVIDERS
    LLM_API_KEY = os.environ.get('LLM_API_KEY') or (
        'mirofish-local-subscription' if _is_subscription_provider else None
    )
    LLM_BASE_URL = (
        'http://127.0.0.1:5001/llm-compat/v1'
        if _is_subscription_provider
        else os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    )
    _configured_llm_model = os.environ.get('LLM_MODEL_NAME', '').strip()
    if LLM_PROVIDER == 'claude_subscription':
        LLM_MODEL_NAME = (
            'sonnet' if not _configured_llm_model or _configured_llm_model == 'qwen-plus'
            else _configured_llm_model
        )
    elif LLM_PROVIDER == 'codex_subscription':
        # Let Codex CLI use the model selected in its own authenticated profile.
        LLM_MODEL_NAME = 'default'
    else:
        LLM_MODEL_NAME = _configured_llm_model or 'gpt-4o-mini'

    if _is_subscription_provider:
        # The OASIS child process inherits these values and uses the same local bridge.
        os.environ['LLM_API_KEY'] = LLM_API_KEY
        os.environ['LLM_BASE_URL'] = LLM_BASE_URL
        os.environ['LLM_MODEL_NAME'] = LLM_MODEL_NAME
    
    # Zep配置
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')
    
    # 文件上传配置
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}
    
    # 文本处理配置
    DEFAULT_CHUNK_SIZE = 500  # 默认切块大小
    DEFAULT_CHUNK_OVERLAP = 50  # 默认重叠大小
    
    # OASIS模拟配置
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')
    
    # OASIS平台可用动作配置
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]
    
    # Report Agent配置
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))
    
    @classmethod
    def validate(cls) -> list[str]:
        """验证必要配置"""
        errors: list[str] = []
        if cls.LLM_PROVIDER == 'api' and not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY 未配置")
        elif cls.LLM_PROVIDER == 'codex_subscription' and not shutil.which('codex'):
            errors.append("Codex CLI non trovato; installalo e accedi con il tuo piano ChatGPT")
        elif cls.LLM_PROVIDER == 'claude_subscription' and not shutil.which('claude'):
            errors.append("Claude Code CLI non trovato; installalo e accedi con il tuo piano Claude")
        elif cls.LLM_PROVIDER not in {'api', *cls.SUBSCRIPTION_PROVIDERS}:
            errors.append("LLM_PROVIDER deve essere api, codex_subscription o claude_subscription")
        if not cls.ZEP_API_KEY:
            errors.append("ZEP_API_KEY 未配置")
        if os.environ.get("ZEP_API_URL"):
            errors.append("ZEP_API_URL 不受支持；MiroFish 仅连接 Zep Cloud")
        if cls.DEBUG:
            import warnings
            warnings.warn("Flask DEBUG mode is enabled. Do not use in production.", RuntimeWarning)
        return errors
