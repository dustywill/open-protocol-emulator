# open-protocol-emulator
This python project emulates an Atlas Copco torque tool for use with for example node-red.

Implemented:
selectPset MID0018
lastTightening MID0061

Work in progress:
disableTool MID0042
enableTool MID0043

Feel free to help out with the implementation of the other MIDs.

You can run multiple instances as long as you change the port

arguments: "-p", "--port"  Port number to listen on (default: 4545)
           "-n", "--name"  Controller name reported in MID 0002 (default: OpenProtocolSim)
    
