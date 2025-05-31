from ..handler import AgentCommand, AgentCommandArg, HandlerRegisterOptions, HandlerBuildConfig, Handler
from ..service import Service

class ShellExec(AgentCommand):
    def __init__(self):
        super().__init__('shell', 'xyz', 'shell <command>', args=[AgentCommandArg('command', True)])

    def build(self, args: dict) -> bytes:
        return b''

config = {
    'sleep': 5,
    'antiDebug': False
}
config = [
    HandlerBuildConfig(name='connec'),
    HandlerBuildConfig(name='sleep', default=5),
    HandlerBuildConfig(name='antiDebug', default=False)
]

options = HandlerRegisterOptions(['x86', 'x64'], ['exe', 'dll'], config, [ShellExec()])

class Shaco(Handler):
    pass

def main():
    agent = Shaco('shaco', 'sh4c0', options)
    service = Service('http://localhost:3000/', '72bbc8893298dc9a9da4cd795e711e51b8da1fd18001b1d248fee6a6feefc332')
    service.run(agent)
main()
