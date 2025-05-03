# Open Protocol (Contoller) Emulator

This project provides a Python-based emulator for an Open Protocol controller, such as an Atlas Copco or Panasonic torque tool. It's designed for testing and development purposes, allowing you to simulate communication with a controller without needing physical hardware. This can be particularly useful for integrating with systems like Node-RED.

## Features

- **Open Protocol Communication:** Emulates key Open Protocol MIDs for communication with a client.
- **Tightening Result Simulation:** Simulates tightening results (MID 0061) with configurable parameters for torque, angle, and OK/NOK status.
- **VIN and Batch Handling:** Supports setting and incrementing VINs and managing batch counts.
- **Pset Management:** Allows selecting and configuring Parameter Sets (Psets) with specific tightening parameters.
- **Tool Control:** Emulates tool enable/disable commands (MID 0042/0043).
- **Graphical User Interface (GUI):** Provides a simple Tkinter GUI for controlling emulator settings and monitoring status.

## Implemented MIDs

- MID 0001: Communication start
- MID 0002: Communication start acknowledge
- MID 0003: Communication stop
- MID 0004: Command error
- MID 0005: Command accepted
- MID 0014: Parameter set selected subscribe
- MID 0015: Parameter set selected
- MID 0016: Parameter set selected acknowledge
- MID 0018: Select Parameter set
- MID 0042: Request tool disable
- MID 0043: Request tool enable
- MID 0050: VIN download request
- MID 0051: VIN subscribe
- MID 0052: VIN
- MID 0053: VIN acknowledge
- MID 0054: VIN unsubscribe
- MID 0060: Last tightening result data subscribe
- MID 0061: Last tightening result data
- MID 0062: Last tightening result acknowledge
- MID 0063: Last tightening result unsubscribe
- MID 9999: Keep alive

## GUI Features

The Python script includes a graphical user interface with the following controls:

- **Global Settings:**
    - Set the initial VIN.
    - Configure the global batch size (used as a fallback if no Pset is selected).
    - Set the percentage of NOK (Not OK) results for simulation.
    - Adjust the interval time between automatic tightening results.
- **Pset Settings:**
    - Select an available Pset ID.
    - Load and apply specific tightening parameters (batch size, target torque, torque min/max, target angle, angle min/max) for the selected Pset.
    - Save Pset parameters to a JSON file.
- **Controls:**
    - Toggle the automatic sending of tightening results.
    - Manually trigger a single tightening result.
- **Status:**
    - Display connection status.
    - Show the current tool protocol status (Enabled/Disabled).
    - Indicate the currently selected Pset.
    - Display the current VIN.
    - Show the current batch progress.

## Getting Started

### Prerequisites

- Python 3.x

### Installation

This project does not have external dependencies beyond the standard Python library.

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/open-protocol-emulator.git
   cd open-protocol-emulator
   ```

### Running the Emulator

You can run the emulator from your terminal:

```bash
python open_protocol_emulator.py
```

This will start the server on the default port (4545) and launch the GUI.

#### Command-line Arguments

You can customize the port and controller name using command-line arguments:

- `-p`, `--port`: Port number to listen on (default: 4545)
- `-n`, `--name`: Controller name reported in MID 0002 (default: OpenProtocolSim)

Example:
```bash
python open_protocol_emulator.py --port 5000 --name MyEmulator
```

## Contributing

Feel free to help out with the implementation of additional MIDs or other features.

## License

GPL-3.0 license
