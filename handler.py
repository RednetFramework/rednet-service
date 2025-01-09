from typing import Any
from base64 import b64decode as dbase64, b64encode as ebase64
from hashlib import sha1
from json import dumps
from gzip import compress as gzCompress, decompress as gzDecompress
from random import randint
from .service import ServiceDefaults
from .rdapi.api import Api
from . import logger

class AgentCommandArg:
    name: str
    required: bool
    file: bool

    def __init__(self, name:str='', required:bool=False, file:bool=False) -> None:
        self.name = name
        self.required = required
        self.file = file

class AgentCommand:
    id: Any
    name: str
    description: str
    help: str
    admin: bool 
    params: list[AgentCommandArg]
    mitr: list[str]

    def __init__(self, name : str, id: Any, description: str= '', help:str = '', admin: bool = False, args: list[AgentCommandArg] = [], mitr : list[str] =  []):
        self.id = id
        self.name = name
        self.description = description
        self.help = help
        self.admin = admin
        self.params = args
        self.mitr = mitr

    def add_arg(self, arg: AgentCommandArg):
        self.params.append(arg)

    def get_dict(self) -> dict:
        paramDict: list[dict] = []

        for param in self.params:
            paramDict.append({
                'name': param.name,
                'required': param.required,
                'file': param.file
            })
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'help': self.help,
            'admin': self.admin,
            'params': paramDict,
            'mitr': self.mitr
        }


    def build(self, args: dict) -> bytes:
        return b''

class HandlerBuildConfig:
    name: str
    input: bool
    altName: str
    default: str | bool | int

    def __init__(self, name: str='', input: bool = False, altName:str = '', default:str | bool | int = False) -> None:
        self.name = name
        self.input = input
        self.default = default
        self.altName = altName

    def get_dict(self):
        return {
            'name': self.name,
            'input': self.input,
            'default': self.default,
            'alt_name': self.altName
        }


class HandlerRegisterOptions:
    arch: list[str]
    formats: list[str]
    configs: list[HandlerBuildConfig]
    commands: list[AgentCommand]
    protocols: list[str] = []

    def __init__(self, arch: list[str], formats: list[str], config: list[HandlerBuildConfig] = [], commands:list[AgentCommand] = [], protocols:list[str] = ['http', 'https']):
        self.arch = arch
        self.formats = formats
        self.configs = config
        self.commands = commands
        self.protocols = protocols

    def add_command(self, command: AgentCommand):
        self.commands.append(command)

    def add_config(self, config: HandlerBuildConfig):
        self.configs.append(config)

    def get_dict(self) -> dict:
        commandDict: list[dict] = []
        for command in self.commands:
            commandDict.append( command.get_dict() )
        configDict: list[dict] = []
        for config in self.configs:
            configDict.append( config.get_dict() )

        return {
            'arch': self.arch,
            'formats': self.formats,
            'config': configDict,
            'protocols': self.protocols,
            'commands': commandDict
        }

class AgentCreateDto:
    handlerID: int
    uid: str
    arch: str
    system: str
    version: str
    p_name: str
    pid: int
    tid: int
    hostname: str
    internal_ip: str
    external_ip: str
    domain: str

    #agent = AgentCreateDto(self.magick, 'windows', '127.0.0.1', '50.50.50.50', arch='x86', domain='dc.local', p_name='default.exe', tid=50, pid=50, hostname='test.local', version='158.158.158')
    def __init__(self, magick: str, uid: str, system: str, internal_ip: str, external_ip: str, arch: str = '', domain: str ='', p_name: str='', tid: int = 0, pid: int = 0, hostname:str = '', version: str =''):
        self.magick = magick.lower()
        self.uid = uid
        self.system = system.lower()
        self.internal_ip = internal_ip
        self.external_ip = external_ip
        self.arch = arch
        self.domain = domain
        self.p_name = p_name
        self.tid = tid
        self.pid = pid
        self.hostname = hostname
        self.version = version

UUID_INT_MAX = 99999999
UUID_INT_MIN = 100

from time import sleep

class Handler(ServiceDefaults):
    name: str
    magick: str
    author: str
    description: str
    registerOptions: HandlerRegisterOptions
    api: Api
    tasks = []


    def __init__(self, name: str, magick: str | bytes, options: HandlerRegisterOptions, author = '', description = ''):
        super().__init__()

        if isinstance(magick, str):
            magick = magick.encode()

        self.name = name
        self.magick = ebase64(magick).decode()
        self.author = author
        self.description = description
        self.registerOptions = options
        super().add_callback('agent', 'response', self.__response__)
        super().add_callback('agent', 'build', self.build)
        super().add_callback('agent', 'command', self.new_task)
        super().add_callback('command', 'execute', self.handle_command)
        super().add_callback('image', 'stream', self.handle_image)
        
    def build(self, data):
        pass

    def _dcompress_b64(self, data):
        return gzDecompress(dbase64(data))
        
    def _compress_b64(self, data: bytes) -> str:
        return ebase64(gzCompress(data)).decode()

    def __response__(self, data: Any):
        logger.debug(f'Server Message: {data}')
        if not 'callbackID' in data:
            logger.warn(f'Invalid server message: {data}')
            return
        try:

            response = self.response(self._dcompress_b64(data['data']))

            if isinstance(response, str):
                response = response.encode()

            response = self._compress_b64(response)

            data['data'] = response

        except Exception as ex:
            logger.error(f'exception on response: {str(ex)}')
            data['data'] = ''
        try:    
            self.ws.send(dumps(data))
        except Exception as ex:
            logger.critical(f'Error on sending data')

    def _uuid_to_bytes(self, uuid: str) -> bytes:
        return bytes.fromhex(uuid.replace('-', ''))

    def _uuid_to_int(self, uuid: str) -> int:
        hash = sha1(self._uuid_to_bytes(uuid)).digest()
        return (int.from_bytes(hash, byteorder='big') % (UUID_INT_MAX - UUID_INT_MIN) + UUID_INT_MIN)

    #TODO: validate id before send to teamserver
    def _random_id(self) -> int:
        return randint(1000, 99999999)

    def register_agent(self, data : AgentCreateDto) -> Any:
        dto = vars(data)

        try:
            return self.api.agent._post(dto, path='')
        except Exception as err:
            logger.error(f'Error on register: {str(err)}')
            return False

    def response(self, response : bytes) -> bytes | str:
        agent = AgentCreateDto(magick=self.magick, uid=str(self._random_id()), system='windows', internal_ip='127.0.0.1', external_ip='50.50.50.50', arch='x86', domain='dc.local', p_name='default.exe', tid=50, pid=50, hostname='test.local', version='158.158.158')
        register_info = self.register_agent(agent)

        if not register_info:
            logger.warn('cannot register agent')
            return b''

        agent.uid

        sleep(1)

        logger.debug(register_info)
        return str(agent.uid)

    def new_task(self, data):
        if not data or not 'agentID' in data or not 'command' in data or not 'args' in data['command']:
            logger.error('invalid task')
            return

        agent = data['agentID']

        for command in self.registerOptions.commands:
            if command.name == data['command']:
                ret = command.build(data['command']['args'])
                self.tasks.append({
                    'agentID': agent,
                    'data': ret
                })
                break

    def get_task(self):
        if self.tasks:
            task = self.tasks.pop(0)
            return task
        return None


    def handle_command(self, data):
        """Handle command execution request via WebSocket
        
        Args:
            data: Command data from WebSocket
        """
        try:
            command = data.get('data', {}).get('command')
            args = data.get('data', {}).get('args', [])
            
            if not command:
                logger.error('Invalid command data')
                return
                
            # Execute command and get response
            response = self.execute_command(command, args)
            
            # Send response back
            self.ws.send(dumps({
                'type': 'command',
                'action': 'response',
                'data': {
                    'command': command,
                    'response': response,
                    'callbackID': data.get('callbackID')
                }
            }))
            
        except Exception as e:
            logger.error(f'Error handling command: {str(e)}')
            # Send error response
            self.ws.send(dumps({
                'type': 'command',
                'action': 'error',
                'data': {
                    'command': command,
                    'error': str(e),
                    'callbackID': data.get('callbackID')
                }
            }))

    def handle_image(self, data):
        """Handle image stream request via WebSocket
        
        Args:
            data: Image data from WebSocket
        """
        try:
            image_data = data.get('data', {}).get('image_data')
            metadata = data.get('data', {}).get('metadata', {})
            
            if not image_data:
                logger.error('Invalid image data')
                return
                
            # Process image data
            processed_data = self.process_image(image_data, metadata)
            
            # Send response back
            self.ws.send(dumps({
                'type': 'image',
                'action': 'response',
                'data': {
                    'image_data': processed_data,
                    'metadata': metadata,
                    'callbackID': data.get('callbackID')
                }
            }))
            
        except Exception as e:
            logger.error(f'Error handling image: {str(e)}')
            # Send error response
            self.ws.send(dumps({
                'type': 'image',
                'action': 'error',
                'data': {
                    'error': str(e),
                    'callbackID': data.get('callbackID')
                }
            }))

    def execute_command(self, command: str, args: list) -> str:
        """Execute a command and return the response
        
        Args:
            command: Command to execute
            args: Command arguments
            
        Returns:
            Command execution response
        """
        # Override this method in your handler implementation
        return f"Command {command} executed with args {args}"

    def process_image(self, image_data: str, metadata: dict) -> str:
        """Process image data and return the result
        
        Args:
            image_data: Base64 encoded image data
            metadata: Image metadata
            
        Returns:
            Processed image data
        """
        # Override this method in your handler implementation
        return image_data

    def get_dict(self) -> dict:
        return {
            'name': self.name,
            'magick': self.magick,
            'author': self.author,
            'description': self.description,
            'options': self.registerOptions.get_dict()
        }
