from time import sleep
from rednet_service.exceptions import ApiResponseException
from rednet_service.service import Service
from rednet_service.listener import Listener


def main():
    listener = Listener('shaco', ['test'])
    listener.add_input('port', 'Port')
    listener.add_input('headers', 'Headers', isArray=True)
    listener.add_input('user-agent', 'User Agent')

    service = Service('https://localhost:3000', '0a9ae824c78e8e1a3d4b995f76c355de93c5ac838059e1b2200d8556a1c692fc')
    service.run(listener, False)
    while True:
        sleep(2)
        try:
            response = listener.transmit('sh4c0', 'teste')
            print('================= response =================')
            print(response)
            print('================= end response =================')
        except ApiResponseException as err:
            print(f'Error: {err}' )
main()
