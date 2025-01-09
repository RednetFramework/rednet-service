import websocket
import pickle
from typing import Any, Callable
from json import loads
from ssl import CERT_NONE
from os.path import exists
from hashlib import sha256
from .rdapi.api import Api
from .rdapi.base import ApiConnection
from . import logger

class ServiceDefaults:

    types: dict = {}
    api = None
    id = -1

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

            logger.debug(f'trying to call: {callback}/{action}')

            if fn := self.get_callback(callback,action):
                fn(msg)

        except Exception as ex:
            logger.error(f'error handling message: {str(ex)}')

    def set_id(self, id : int):
        self.id = id

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

    def __init__(self, url: str, password: str):
        if not url.startswith('http://') and not url.startswith('https://'):
            raise Exception('Invalid Endpoint')

        if url.endswith('/'):
            url = url[:-1]

        self.base_url = url
        self.password = sha256(password.encode()).hexdigest()

    def _get_ws_url(self, base_url: str, endpoint:str):
        return base_url.replace('https://', 'wss://').replace('http://', 'ws://') + f'/ws/{endpoint}'

    def _save_auth(self, token: str, uuid: str):
        auth_object = {
            'token': token,
            'uuid': uuid
        }
        with open(f'{self.agent.endpoint}.auth', 'wb') as f:
            pickle.dump(auth_object, f)
        
    def _get_auth(self):
        try:
            if exists(f'{self.agent.endpoint}.auth'):
                with open(f'{self.agent.endpoint}.auth', 'rb') as f:
                    return pickle.load(f)
        except Exception as err:
            logger.error(f'Error on get auth: {str(err)}')
            return None
            
        return None

    def _ws_msg(self, ws, msg):
        logger.debug('new message from server')
        try:
            msg_data = loads(msg)
            msg_type = msg_data.get('type')
            
            # Handle command execution
            if msg_type == 'command' and msg_data.get('action') == 'execute':
                self._handle_command(msg_data)
            # Handle image streaming
            elif msg_type == 'image' and msg_data.get('action') == 'stream':
                self._handle_image_stream(msg_data)
            # Handle other messages
            elif self.agent:
                self.agent.handle(msg)
        except Exception as e:
            logger.error(f'Error handling message: {str(e)}')

    def _ws_close(self, *args):
        logger.critical('Websocket closed, exiting...')
        exit(1)

    def _ws_err(self, ws, error):
        logger.critical(f'Websocket Error {error}')
        exit(1)

    def _connect_websocket(self, token):
        if token:
            ws_url = self._get_ws_url(self.base_url, self.agent.endpoint)
            logger.info(f'websocket url: {ws_url}')

            self.ws = websocket.WebSocketApp(
                url=ws_url,
                header={ 'Authorization' : f'Bearer {token}'},
                on_error=self._ws_err,
                on_message=self._ws_msg,
                on_close=self._ws_close
            )
            self.agent.set_ws(self.ws)
            
            # Add command and image handlers if supported
            if hasattr(self.agent, 'handle_command'):
                self.agent.add_callback('command', 'execute', self.agent.handle_command)
            if hasattr(self.agent, 'handle_image'):
                self.agent.add_callback('image', 'stream', self.agent.handle_image)
                
            self.ws.run_forever(sslopt={'cert_reqs': CERT_NONE})

    def _authenticate(self, save = False):
        
        logger.info(f'Authenticating on url: {self.base_url}')
        res = self._get_auth()
        uuid = ''
        if res:
            uuid = res['uuid']
        self.api = Api(ApiConnection(self.base_url))
        response: Any = self.api.auth.auth(self.agent.endpoint, '', self.password, data=self.agent.get_dict(),uuid=uuid)

        token = response['token']
        uuid = response['uuid']
        id = response['id']

        self._save_auth(token, uuid)
        self.api.add_token(token)
        self.agent.set_api(self.api)
        self.agent.set_id(id)

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
