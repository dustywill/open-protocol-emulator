# open-protocol-emulator
This python project emulates an Atlas Copco torque tool for use with for example node-red.

Implemented:
selectPset MID0018
lastTightening MID0061
disableTool MID0042
enableTool MID0043

The python script has a graphical UI:

* Setting the VIN, batch size and percentage of NOK's versus OK's, and Interval time between automatic results 
* Toggle automatic mode: a tighening result will be emulated with an OK or NOK periodically
* Send Single result: force a single tightening result

Please, Feel free to help out with the implementation of the other MIDs.

You can run multiple instances as long as you change the port

arguments: 

           "-p", "--port"  Port number to listen on (default: 4545)

           "-n", "--name"  Controller name reported in MID 0002 (default: OpenProtocolSim)
    
