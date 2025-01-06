import os
import json
import logging
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, Union
from pathlib import Path

@dataclass
class LoggingConfig:
    level: str = 'INFO'
    format: str = '%(log_color)s%(levelname)-8s%(reset)s %(message)s'
    date_format: str = '%Y-%m-%d %H:%M:%S'
    colors: Dict[str, str] = None

    def __post_init__(self):
        if self.colors is None:
            self.colors = {
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white'
            }

@dataclass
class SSLConfig:
    enabled: bool = False
    verify: bool = True
    ca_file: Optional[str] = None
    client_cert: Optional[str] = None
    client_key: Optional[str] = None

@dataclass
class RetryConfig:
    max_attempts: int = 3
    delay: float = 1.0
    backoff: float = 2.0
    max_delay: float = 30.0

@dataclass
class WebSocketConfig:
    ping_interval: float = 30.0
    ping_timeout: float = 10.0
    close_timeout: float = 5.0
    max_size: int = 10 * 1024 * 1024  # 10MB
    compression: Optional[str] = None

@dataclass
class ServiceConfig:
    # Environment
    data_dir: str = 'data'
    env: str = 'development'

    # Server connection
    server_url: str = 'http://localhost:3000'
    api_prefix: str = ''
    ws_prefix: str = '/ws'

    # Authentication
    auth_file: str = 'auth.json'
    password: Optional[str] = None

    # SSL/TLS
    ssl: SSLConfig = SSLConfig()

    # Retry settings
    retry: RetryConfig = RetryConfig()

    # WebSocket settings
    websocket: WebSocketConfig = WebSocketConfig()

    # Logging
    logging: LoggingConfig = LoggingConfig()

    def __post_init__(self):
        # Initialize nested dataclasses if they're dictionaries
        if isinstance(self.ssl, dict):
            self.ssl = SSLConfig(**self.ssl)
        if isinstance(self.retry, dict):
            self.retry = RetryConfig(**self.retry)
        if isinstance(self.websocket, dict):
            self.websocket = WebSocketConfig(**self.websocket)
        if isinstance(self.logging, dict):
            self.logging = LoggingConfig(**self.logging)

    @classmethod
    def from_env(cls) -> 'ServiceConfig':
        """Create configuration from environment variables."""
        config_dict = {
            'data_dir': os.getenv('REDNET_DATA_DIR', 'data'),
            'env': os.getenv('REDNET_ENV', 'development'),
            'server_url': os.getenv('REDNET_SERVER_URL', 'http://localhost:3000'),
            'api_prefix': os.getenv('REDNET_API_PREFIX', ''),
            'ws_prefix': os.getenv('REDNET_WS_PREFIX', '/ws'),
            'auth_file': os.getenv('REDNET_AUTH_FILE', 'auth.json'),
            'password': os.getenv('REDNET_PASSWORD'),
            'ssl': {
                'enabled': os.getenv('REDNET_SSL_ENABLED', '').lower() == 'true',
                'verify': os.getenv('REDNET_SSL_VERIFY', '').lower() != 'false',
                'ca_file': os.getenv('REDNET_SSL_CA_FILE'),
                'client_cert': os.getenv('REDNET_SSL_CLIENT_CERT'),
                'client_key': os.getenv('REDNET_SSL_CLIENT_KEY')
            },
            'retry': {
                'max_attempts': int(os.getenv('REDNET_RETRY_MAX_ATTEMPTS', '3')),
                'delay': float(os.getenv('REDNET_RETRY_DELAY', '1.0')),
                'backoff': float(os.getenv('REDNET_RETRY_BACKOFF', '2.0')),
                'max_delay': float(os.getenv('REDNET_RETRY_MAX_DELAY', '30.0'))
            },
            'websocket': {
                'ping_interval': float(os.getenv('REDNET_WS_PING_INTERVAL', '30.0')),
                'ping_timeout': float(os.getenv('REDNET_WS_PING_TIMEOUT', '10.0')),
                'close_timeout': float(os.getenv('REDNET_WS_CLOSE_TIMEOUT', '5.0')),
                'max_size': int(os.getenv('REDNET_WS_MAX_SIZE', str(10 * 1024 * 1024))),
                'compression': os.getenv('REDNET_WS_COMPRESSION')
            },
            'logging': {
                'level': os.getenv('REDNET_LOG_LEVEL', 'INFO'),
                'format': os.getenv('REDNET_LOG_FORMAT', '%(log_color)s%(levelname)-8s%(reset)s %(message)s'),
                'date_format': os.getenv('REDNET_LOG_DATE_FORMAT', '%Y-%m-%d %H:%M:%S')
            }
        }
        return cls(**config_dict)

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> 'ServiceConfig':
        """Load configuration from a JSON file."""
        with open(path, 'r') as f:
            config_dict = json.load(f)
        return cls(**config_dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to a dictionary."""
        return {
            k: asdict(v) if hasattr(v, '__dataclass_fields__') else v
            for k, v in asdict(self).items()
        }

    def save(self, path: Union[str, Path]) -> None:
        """Save configuration to a JSON file."""
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=4)

    def setup_logging(self) -> None:
        """Configure logging based on the current settings."""
        try:
            from colorlog import ColoredFormatter
            formatter = ColoredFormatter(
                self.logging.format,
                datefmt=self.logging.date_format,
                log_colors=self.logging.colors
            )
        except ImportError:
            formatter = logging.Formatter(
                self.logging.format.replace('%(log_color)s', '').replace('%(reset)s', ''),
                datefmt=self.logging.date_format
            )

        handler = logging.StreamHandler()
        handler.setFormatter(formatter)

        logger = logging.getLogger()
        logger.setLevel(self.logging.level.upper())
        logger.handlers = []
        logger.addHandler(handler)

# Create default configuration
config = ServiceConfig.from_env()