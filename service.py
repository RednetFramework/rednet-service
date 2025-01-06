import websocket
import pickle
import json
from typing import Any, Callable, Optional, Dict
from json import loads
from ssl import CERT_NONE, create_default_context
from os.path import exists, join
from hashlib import sha256
from .rdapi.api import Api
from .rdapi.base import ApiConnection
from . import logger
from .config import config, ServiceConfig

class ServiceDefaults:
    types: dict = {}
    api = None
    id = -1
    uuid = None

    def __init__(self, endpoint: str = 'handler'):
        self.endpoint = endpoint 

    def handle(self, msg):
        try:
            msg = loads(msg)
            if not 'type' in msg or not 'data' in msg or not 'action' in msg:
                logger.error('invalid server data')
                return

            callback = msg['type']
            action = msg['action']
            data = msg['data']

            logger.debug(f'trying to call: {callback}/{action}')

            if fn := self.get_callback(callback, action):
                if callback == 'command' and action == 'execute':
                    # Handle command execution
                    command_uuid = data.get('uuid')
                    command_type = data.get('type', 'shell')
                    command = data.get('command')
                    timeout = data.get('timeout', 60)
                    metadata = data.get('metadata', {})

                    try:
                        result = fn(command, command_type, timeout, metadata)
                        # Update command status
                        if self.api:
                            self.api.command.update_status(
                                command_uuid,
                                'completed',
                                output=str(result),
                                exit_code=0
                            )
                    except Exception as e:
                        logger.error(f'Command execution error: {str(e)}')
                        if self.api:
                            self.api.command.update_status(
                                command_uuid,
                                'failed',
                                error=str(e),
                                exit_code=1
                            )
                else:
                    fn(msg)

        except Exception as ex:
            logger.error(f'error handling message: {str(ex)}')

    def set_id(self, id : int):
        self.id = id

    def set_uuid(self, uuid: str):
        self.uuid = uuid

    def set_ws(self, ws):
        self.ws = ws

    def set_api(self, api: Api):
        self.api = api

    def add_callback(self, callback: str, action: str, fn: Callable):
        logger.debug(f'setting new action: {callback} / {action}')
        if callback not in self.types:
            self.types[callback] = {}

        self.types[callback][action] = fn

    def get_callback(self, callback: str, action: str) -> Callable | None:
        if callback in self.types:
            if action in self.types[callback]:
                return self.types[callback][action]
            
        return None

    def get_dict(self) -> dict:
        return {}

class Service:

    def __init__(self, url: Optional[str] = None, password: Optional[str] = None, config_file: Optional[str] = None):
        """Initialize the service with either explicit parameters or configuration."""
        if config_file:
            self.config = ServiceConfig.from_file(config_file)
        else:
            self.config = config

        # Override config with explicit parameters if provided
        if url:
            self.config.server_url = url
        if password:
            self.config.password = password

        # Validate URL
        if not self.config.server_url.startswith('http://') and not self.config.server_url.startswith('https://'):
            raise Exception('Invalid Endpoint URL')

        if self.config.server_url.endswith('/'):
            self.config.server_url = self.config.server_url[:-1]

        # Set up logging
        self.config.setup_logging()

        # Initialize base URL and password
        self.base_url = self.config.server_url
        if not self.config.password:
            raise Exception('Password is required')
        self.password = sha256(self.config.password.encode()).hexdigest()

    def _get_ws_url(self, base_url: str, endpoint: str) -> str:
        """Get WebSocket URL from base URL and endpoint."""
        ws_url = base_url.replace('https://', 'wss://').replace('http://', 'ws://')
        return f"{ws_url}{self.config.ws_prefix}/{endpoint}"

    def _save_auth(self, token: str, uuid: str) -> None:
        """Save authentication data to a file."""
        auth_object = {
            'token': token,
            'uuid': uuid,
            'endpoint': self.agent.endpoint
        }
        auth_path = join(self.config.data_dir, self.config.auth_file)
        os.makedirs(os.path.dirname(auth_path), exist_ok=True)
        with open(auth_path, 'w') as f:
            json.dump(auth_object, f, indent=4)
        
    def _get_auth(self) -> Optional[Dict[str, str]]:
        """Load authentication data from file."""
        try:
            auth_path = join(self.config.data_dir, self.config.auth_file)
            if exists(auth_path):
                with open(auth_path, 'r') as f:
                    auth_data = json.load(f)
                    if auth_data.get('endpoint') == self.agent.endpoint:
                        return auth_data
        except Exception as err:
            logger.error(f'Error loading auth data: {str(err)}')
        return None

    def _ws_msg(self, ws, msg):
        logger.debug('new message from server')
        if self.agent:
            self.agent.handle(msg)

    def _ws_close(self, *args):
        logger.critical('Websocket closed, exiting...')
        exit(1)

    def _ws_err(self, ws, error):
        logger.critical(f'Websocket Error {error}')
        exit(1)

    def _connect_websocket(self, token: str) -> None:
        """Establish WebSocket connection with the server."""
        if not token:
            return

        ws_url = self._get_ws_url(self.base_url, self.agent.endpoint)
        logger.info(f'WebSocket URL: {ws_url}')

        # Prepare SSL options
        ssl_opts = {}
        if self.config.ssl.enabled:
            if not self.config.ssl.verify:
                ssl_opts['cert_reqs'] = CERT_NONE
            if self.config.ssl.ca_file:
                ssl_opts['ca_certs'] = self.config.ssl.ca_file
            if self.config.ssl.client_cert and self.config.ssl.client_key:
                ssl_opts['certfile'] = self.config.ssl.client_cert
                ssl_opts['keyfile'] = self.config.ssl.client_key

        # Create WebSocket connection
        self.ws = websocket.WebSocketApp(
            url=ws_url,
            header={'Authorization': f'Bearer {token}'},
            on_error=self._ws_err,
            on_message=self._ws_msg,
            on_close=self._ws_close
        )
        self.agent.set_ws(self.ws)

        # Configure WebSocket options
        ws_opts = {
            'ping_interval': self.config.websocket.ping_interval,
            'ping_timeout': self.config.websocket.ping_timeout,
            'max_size': self.config.websocket.max_size
        }

        if self.config.websocket.compression:
            ws_opts['subprotocols'] = [self.config.websocket.compression]

        # Run WebSocket connection
        self.ws.run_forever(
            sslopt=ssl_opts if ssl_opts else None,
            **ws_opts
        )

    def _authenticate(self, save = False):
        logger.info(f'Authenticating on url: {self.base_url}')
        res = self._get_auth()
        uuid = ''
        if res:
            uuid = res['uuid']
        self.api = Api(ApiConnection(self.base_url))
        
        # Get agent data
        agent_data = self.agent.get_dict()
        agent_data.update({
            'active': True,
            'last_seen': None
        })
        
        # Authenticate
        response: Any = self.api.auth.auth(
            self.agent.endpoint,
            '',
            self.password,
            data=agent_data,
            uuid=uuid
        )

        # Extract response data
        token = response['token']
        uuid = response['uuid']
        id = response['id']

        # Save and configure
        self._save_auth(token, uuid)
        self.api.add_token(token)
        self.agent.set_api(self.api)
        self.agent.set_id(id)
        self.agent.set_uuid(uuid)

        return token

    def run(self, agent: ServiceDefaults, ws = True, save = False):
        logger.debug('Authenticating on webserver')
        try:
            self.agent = agent
            token = self._authenticate(save)
            if ws:
                self._connect_websocket(token)
        except Exception as err:
            logger.error(f'Error: {str(err)}')
