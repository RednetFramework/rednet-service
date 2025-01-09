from base64 import b64encode as ebase64, b64decode as dbase64
from gzip import compress as gzCompress, decompress as gzDecompress
from .service import ServiceDefaults
from . import logger

class ListenerAgentBuildInput:
    id: str #for identify in handler build
    name: str #for show in client
    isArray = False # if you have array, you not have combo
    isCombo = False # if you have combo, you not have array
    comboValues: list = [] # only if you have combo

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class Listener(ServiceDefaults):
    def __init__(self, name: str, protocols: list[str], description:str = '', port: int = 1, support_socks = False, support_changes = False):
        super().__init__('listener')
        self.name = name
        self.protocols = protocols
        self.description = description
        self.port = port
        self.inputs = []
        self.support_socks = support_socks
        self.support_changes = support_changes

    def _dcompress_b64(self, data) -> bytes:
        return gzDecompress(dbase64(data))

    def _compress_b64(self, data : bytes) -> str:
        return ebase64(gzCompress(data)).decode()

    def transmit(self, magick : bytes | str, data: bytes | str):
        """Transmit data using WebSocket if connected, fallback to HTTP"""
        if isinstance(magick, str):
            magick = magick.encode()

        if isinstance(data, str):
            data = data.encode()

        magick = ebase64(magick).decode()
        data = self._compress_b64(data)

        # Try WebSocket first
        if hasattr(self, 'ws'):
            try:
                self.ws.send(dumps({
                    'type': 'listener',
                    'action': 'response',
                    'data': {
                        'magick': magick,
                        'payload': data
                    }
                }))
                return None  # WebSocket is async, no response needed
            except Exception as e:
                logger.error(f'WebSocket transmit failed: {str(e)}')
                # Fall through to HTTP

        # Fallback to HTTP
        if self.api:
            return self._dcompress_b64(self.api.listener.transmit(magick, data))
        else:
            raise Exception('API not set')

    def add_input(self, id: str, name: str, isArray = False, isCombo = False, comboValues = []):
        self.inputs.append(ListenerAgentBuildInput(id=id, name=name, isArray=isArray, isCombo=isCombo, comboValues=comboValues))
    
    def get_dict(self) -> dict:

        input_dict:list[dict] = []

        for input in self.inputs:
            input_dict.append(vars(input))

        return {
            'name': self.name,
            'protocol': self.protocols,
            'description': self.description,
            'options': {
                'inputs': input_dict,
                'support' : {
                    'changes': self.support_changes,
                    'socks': self.support_socks
                }
            }
        }
