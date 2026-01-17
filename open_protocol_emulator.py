#!/usr/bin/env python3
import socket
import threading
import time
import datetime
import random
import tkinter as tk
from tkinter import messagebox
import re # Import regex for VIN parsing
import argparse # For command-line arguments

# Helper: Build an Open Protocol message.
def build_message(mid: int, rev: int = 1, data: str = "", no_ack: bool = False,
                  station: str = "00", spindle: str = "00") -> bytes:
    """
    Construct an Open Protocol message.
    - mid: Message ID (e.g., 1 for MID 0001).
    - rev: Message revision (default 1).
    - data: Data field (ASCII string).
    - no_ack: If True, sets the NoAck flag (1 = no ack needed, 0 = ack required).
    - station and spindle: Two-digit strings.
    Returns a bytes object including the proper length header and NUL terminator.
    """
    mid_str = f"{mid:04d}"
    rev_str = f"{rev:03d}"
    ack_flag = "1" if no_ack else "0"
    spare = "    "  # 4 spaces reserved
    body = f"{mid_str}{rev_str}{ack_flag}{station}{spindle}{spare}{data}"
    # Length: header (4 digits for length field + body) without terminating NUL.
    length_value = 4 + len(body)
    length_str = f"{length_value:04d}"
    message = f"{length_str}{body}\x00"
    return message.encode('ascii')

class OpenProtocolEmulator:
    # Maximum supported revision per MID
    MAX_REV_0002 = 6
    MAX_REV_0004 = 3
    MAX_REV_0015 = 2
    MAX_REV_0041 = 5
    MAX_REV_0052 = 2
    MAX_REV_0061 = 7
    MAX_REV_0101 = 5

    # Added port and name to constructor with defaults
    def __init__(self, host='0.0.0.0', port=4545, controller_name="OpenProtocolSim"):
        self.host = host
        self.port = port # Use passed-in port
        self.controller_name = controller_name.ljust(25)[:25] # Use passed-in name, ensure length

        self.state_lock = threading.RLock()

        self._session_active = False
        self._tool_enabled = True
        self._auto_send_loop_active = True
        self.current_pset = None
        self.available_psets = {"001", "002", "003", "004", "005",
                                "010", "011", "012", "013", "014", "015", 
                                "050", "051", "052", "053", "054", "055", 
                                "100", "101", "102", "103", "104", "105"}
        self.current_pset = None
        # --- VIN and Batch State ---
        self.current_vin = "AB123000"
        self.vin_prefix = "AB123"
        self.vin_numeric_str = "000"
        self.vin_padding = 3
        self.target_batch_size = 5
        self.batch_counter = 0
        self.nok_probability = 0.3
        # VIN 4-part identifier (for MID 0052 revision 2)
        self.identifier_part2 = ""
        self.identifier_part3 = ""
        self.identifier_part4 = ""
        # --- End VIN and Batch State ---
        self.vin_subscribed = False
        self.vin_no_ack = False
        self.vin_subscribed_rev = 1
        self.result_subscribed = False
        self.result_no_ack = False
        self.result_subscribed_rev = 1
        # --- Multi-spindle State ---
        self.multi_spindle_subscribed = False
        self.multi_spindle_no_ack = False
        self.multi_spindle_requested_rev = 1
        self.sync_tightening_id = 0
        self.num_spindles = 2
        # --- End Multi-spindle State ---
        # Extended tightening result data (for MID 0061 rev 3+)
        self.strategy_code = 0
        self.strategy_options = "00000"
        self.tightening_error_status_2 = 0
        self.stage_result_count = 0
        self.auto_loop_interval = 20
        self.pset_last_change = None
        self.pset_subscribed = False
        self.pset_subscribed_rev = 1
        self.pset_ok_counter = 0
        self.client_socket = None
        self.send_lock = threading.Lock()
        self.tightening_id_counter = 0
        self.controller_time = None

        # --- Controller Info for MID 0002 Revisions 2+ ---
        self.supplier_code = 1
        self.op_version = "2.8.0              "
        self.ctrl_sw_version = "1.0.0              "
        self.tool_sw_version = "1.0.0              "
        self.rbu_type = "                        "
        self.ctrl_serial = "SN12345678"
        self.system_type = "PF6000    "
        self.system_subtype = "          "
        self.seq_num_support = 0
        self.link_support = 0
        self.station_id = "0001      "
        self.station_name = "Station                  "
        self.client_id = 1
        # --- End Controller Info ---

        # --- Tool Info for MID 0041 Revisions 2+ ---
        self.tool_serial_number = "TOOL123456789012"
        self.tool_number_of_tightenings = 0
        self.tool_last_calib_date = "2025-01-01"
        self.tool_controller_serial = self.ctrl_serial
        self.tool_calib_value = 10000
        self.tool_last_service_date = "2025-01-01"
        self.tool_tightenings_since_service = 0
        self.tool_type = 1
        self.tool_motor_size = 100
        self.tool_open_end_data = "                    "
        self.tool_controller_software_version = self.ctrl_sw_version
        # --- End Tool Info ---

        # --- Pset Parameters Storage ---
        self.pset_parameters = {}
        self._load_pset_parameters(self.controller_name) # Attempt to load from file using controller name
        # --- End Pset Parameters Storage ---

        self._parse_vin(self.current_vin)

        # --- MID Handler Registry ---
        self.mid_handlers = {}
        self._register_mid_handlers()
        # --- End MID Handler Registry ---

    @property
    def session_active(self):
        with self.state_lock:
            return self._session_active

    @session_active.setter
    def session_active(self, value):
        with self.state_lock:
            self._session_active = value

    @property
    def tool_enabled(self):
        with self.state_lock:
            return self._tool_enabled

    @tool_enabled.setter
    def tool_enabled(self, value):
        with self.state_lock:
            self._tool_enabled = value

    @property
    def auto_send_loop_active(self):
        with self.state_lock:
            return self._auto_send_loop_active

    @auto_send_loop_active.setter
    def auto_send_loop_active(self, value):
        with self.state_lock:
            self._auto_send_loop_active = value

    def _register_mid_handlers(self):
        self.mid_handlers = {
            1: self._handle_mid_0001,
            3: self._handle_mid_0003,
            4: self._handle_mid_0004,
            5: self._handle_mid_0005,
            9999: self._handle_mid_9999,
            14: self._handle_mid_0014,
            16: self._handle_mid_0016,
            17: self._handle_mid_0017,
            18: self._handle_mid_0018,
            40: self._handle_mid_0040,
            41: self._handle_mid_0041,
            42: self._handle_mid_0042,
            43: self._handle_mid_0043,
            50: self._handle_mid_0050,
            51: self._handle_mid_0051,
            53: self._handle_mid_0053,
            54: self._handle_mid_0054,
            60: self._handle_mid_0060,
            62: self._handle_mid_0062,
            63: self._handle_mid_0063,
            82: self._handle_mid_0082,
        }

    def _get_response_revision(self, mid: int, requested_rev: int) -> int:
        """Return highest supported revision <= requested."""
        max_supported = {
            2: self.MAX_REV_0002,
            4: self.MAX_REV_0004,
            15: self.MAX_REV_0015,
            41: self.MAX_REV_0041,
            52: self.MAX_REV_0052,
            61: self.MAX_REV_0061,
        }
        max_rev = max_supported.get(mid, 1)
        return min(requested_rev, max_rev)

    def _build_mid0002_data(self, revision: int) -> str:
        """Build MID 0002 response data for given revision (1-6)."""
        fields = []

        fields.append(f"01{1:04d}")
        fields.append(f"02{1:02d}")
        fields.append(f"03{self.controller_name}")

        if revision >= 2:
            fields.append(f"04{self.supplier_code:03d}")
            fields.append(f"05{self.op_version}")
            fields.append(f"06{self.ctrl_sw_version}")
            fields.append(f"07{self.tool_sw_version}")

        if revision >= 3:
            fields.append(f"08{self.rbu_type}")
            fields.append(f"09{self.ctrl_serial}")

        if revision >= 4:
            fields.append(f"10{self.system_type}")
            fields.append(f"11{self.system_subtype}")

        if revision >= 5:
            fields.append(f"12{self.seq_num_support:01d}")
            fields.append(f"13{self.link_support:01d}")
            fields.append(f"14{self.station_id}")
            fields.append(f"15{self.station_name}")

        if revision >= 6:
            fields.append(f"16{self.client_id:01d}")

        return "".join(fields)

    def _build_mid0004_data(self, revision: int, mid: int, error_code: int, extra_text: str = "") -> str:
        """Build MID 0004 error response data for given revision (1-3)."""
        fields = []

        fields.append(f"{mid:04d}")
        fields.append(f"{error_code:02d}")

        if revision >= 2:
            fields.append(f"{mid:04d}")

        if revision >= 3:
            fields.append(f"{extra_text.ljust(25)[:25]}")

        return "".join(fields)

    # === Communication MID Handlers ===

    def _handle_mid_0001(self, mid_int, rev, no_ack_flag, data_field, msg):
        if self.session_active:
            error_data = self._build_mid0004_data(1, 1, 96)
            resp = build_message(4, rev=1, data=error_data)
        else:
            requested_rev = int(rev) if rev.strip() else 1
            response_rev = self._get_response_revision(2, requested_rev)
            data = self._build_mid0002_data(response_rev)
            resp = build_message(2, rev=response_rev, data=data)
            self.session_active = True
            print(f"[Session] Communication started (rev {response_rev}).")
            threading.Thread(target=self.send_tightening_results_loop, daemon=True).start()
        self.send_to_client(resp)

    def _handle_mid_0003(self, mid_int, rev, no_ack_flag, data_field, msg):
        resp = build_message(5, rev=1, data="0003")
        self.send_to_client(resp)
        print("[Session] Communication stop received. Ending session.")
        self.session_active = False
        self.vin_subscribed = False
        self.result_subscribed = False
        self.pset_subscribed = False
        self.pset_subscribed_rev = 1
        try:
            if self.client_socket:
                self.client_socket.close()
        except OSError:
            pass
        self.client_socket = None

    def _handle_mid_0004(self, mid_int, rev, no_ack_flag, data_field, msg):
        print(f"[Info] Received MID 0004 from client: Data='{data_field}' (ignored).")

    def _handle_mid_0005(self, mid_int, rev, no_ack_flag, data_field, msg):
        print(f"[Info] Received MID 0005 from client: Data='{data_field}' (ignored).")

    def _handle_mid_9999(self, mid_int, rev, no_ack_flag, data_field, msg):
        print("[KeepAlive] Received keep-alive message.")
        resp = build_message(9999, rev=1)
        self.send_to_client(resp)
        print("[KeepAlive] Echo back keep-alive message.")
    # === Parameter Set MID Handlers ===

    def _handle_mid_0014(self, mid_int, rev, no_ack_flag, data_field, msg):
        if self.pset_subscribed:
            error_data = self._build_mid0004_data(1, 14, 6)
            resp = build_message(4, rev=1, data=error_data)
        else:
            requested_rev = int(rev) if rev.strip() else 1
            subscribed_rev = self._get_response_revision(15, requested_rev)
            self.pset_subscribed_rev = subscribed_rev
            self.pset_subscribed = True
            resp = build_message(5, rev=1, data="0014")
            print(f"[Pset] Pset subscription accepted (will send MID 0015 rev {subscribed_rev}).")
            if self.current_pset:
                mid15_data = self._build_mid0015_data(self.pset_subscribed_rev)
                mid15_msg = build_message(15, rev=self.pset_subscribed_rev, data=mid15_data)
                self.send_to_client(mid15_msg)
                print(f"[Pset] Sent current Pset (MID 0015 rev {self.pset_subscribed_rev}): {self.current_pset}")
        self.send_to_client(resp)

    def _handle_mid_0016(self, mid_int, rev, no_ack_flag, data_field, msg):
        print("[Pset] Pset selected acknowledged by client (MID 0016).")

    def _handle_mid_0017(self, mid_int, rev, no_ack_flag, data_field, msg):
        if self.pset_subscribed:
            self.pset_subscribed = False
            self.pset_subscribed_rev = 1
            resp = build_message(5, rev=1, data="0017")
            print("[Pset] Unsubscribed from Pset selection.")
        else:
            error_data = self._build_mid0004_data(1, 17, 7)
            resp = build_message(4, rev=1, data=error_data)
        self.send_to_client(resp)

    def _handle_mid_0018(self, mid_int, rev, no_ack_flag, data_field, msg):
        pset_id = data_field.strip()
        if pset_id == "0" or pset_id == "000":
            self.current_pset = "0"
            self.pset_last_change = datetime.datetime.now()
            self.pset_ok_counter = 0
            resp = build_message(5, rev=1, data="0018")
            print("[Pset] No Pset selected (Pset 0).")
            if self.pset_subscribed:
                mid15_data = self._build_mid0015_data(self.pset_subscribed_rev)
                mid15_msg = build_message(15, rev=self.pset_subscribed_rev, data=mid15_data)
                self.send_to_client(mid15_msg)
                print(f"[Pset] Sent MID 0015 rev {self.pset_subscribed_rev}: Pset 0")
        elif pset_id in self.available_psets:
            self.current_pset = pset_id
            self.pset_last_change = datetime.datetime.now()
            self.pset_ok_counter = 0
            resp = build_message(5, rev=1, data="0018")
            print(f"[Pset] Pset {pset_id} selected.")
            if self.pset_subscribed:
                mid15_data = self._build_mid0015_data(self.pset_subscribed_rev)
                mid15_msg = build_message(15, rev=self.pset_subscribed_rev, data=mid15_data)
                self.send_to_client(mid15_msg)
                print(f"[Pset] Sent MID 0015 rev {self.pset_subscribed_rev}: {self.current_pset}")
        else:
            error_data = self._build_mid0004_data(1, 18, 2)
            resp = build_message(4, rev=1, data=error_data)
        self.send_to_client(resp)
    # === Tool Control MID Handlers ===

    def _handle_mid_0040(self, mid_int, rev, no_ack_flag, data_field, msg):
        requested_rev = int(rev) if rev.strip() else 1
        response_rev = self._get_response_revision(41, requested_rev)
        tool_data = self._build_mid0041_data(response_rev)
        resp = build_message(41, rev=response_rev, data=tool_data)
        self.send_to_client(resp)
        print(f"[Tool] Sent tool data (MID 0041 rev {response_rev})")

    def _handle_mid_0041(self, mid_int, rev, no_ack_flag, data_field, msg):
        print("[Tool] Received MID 0041 from client (unexpected - this is a controller response). Ignoring.")

    def _handle_mid_0042(self, mid_int, rev, no_ack_flag, data_field, msg):
        print("[Tool] Received Request Tool Disable (MID 0042).")
        self.tool_enabled = False
        resp = build_message(5, rev=1, data="0042")
        self.send_to_client(resp)
        notification = build_message(40, rev=1)
        self.send_to_client(notification)
        print("[Tool] Tool Disabled. Sent MID 0005 ack and MID 0040 notification.")

    def _handle_mid_0043(self, mid_int, rev, no_ack_flag, data_field, msg):
        print("[Tool] Received Request Tool Enable (MID 0043).")
        self.tool_enabled = True
        resp = build_message(5, rev=1, data="0043")
        self.send_to_client(resp)
        notification = build_message(41, rev=1)
        self.send_to_client(notification)
        print("[Tool] Tool Enabled. Sent MID 0005 ack and MID 0041 notification.")
    # === VIN MID Handlers ===

    def _handle_mid_0050(self, mid_int, rev, no_ack_flag, data_field, msg):
        vin = data_field.strip()
        print(f"[VIN] Received VIN download: {vin}")
        if self._parse_vin(vin):
            self.current_vin = vin
            with self.state_lock:
                self.batch_counter = 0
            print("[VIN] Batch counter reset due to new VIN.")
        resp = build_message(5, rev=1, data="0050")
        self.send_to_client(resp)
        if self.vin_subscribed:
            vin_data = self._build_mid0052_data(self.vin_subscribed_rev)
            vin_msg = build_message(52, rev=self.vin_subscribed_rev, data=vin_data, no_ack=self.vin_no_ack)
            self.send_to_client(vin_msg)
            print(f"[VIN] Sent VIN update (MID 0052 rev {self.vin_subscribed_rev}): {self.current_vin}")

    def _handle_mid_0051(self, mid_int, rev, no_ack_flag, data_field, msg):
        req_rev = int(rev) if rev.strip() else 1
        if self.vin_subscribed:
            error_data = self._build_mid0004_data(1, 51, 6)
            resp = build_message(4, rev=1, data=error_data)
        else:
            subscribed_rev = self._get_response_revision(52, req_rev)
            self.vin_subscribed_rev = subscribed_rev
            self.vin_subscribed = True
            self.vin_no_ack = (no_ack_flag == "1")
            resp = build_message(5, rev=1, data="0051")
            print(f"[VIN] Subscription accepted (will send MID 0052 rev {subscribed_rev}).")
            if self.current_vin:
                vin_data = self._build_mid0052_data(self.vin_subscribed_rev)
                vin_msg = build_message(52, rev=self.vin_subscribed_rev, data=vin_data, no_ack=self.vin_no_ack)
                self.send_to_client(vin_msg)
                print(f"[VIN] Sent current VIN (MID 0052 rev {self.vin_subscribed_rev}): {self.current_vin}")
        self.send_to_client(resp)

    def _handle_mid_0053(self, mid_int, rev, no_ack_flag, data_field, msg):
        print("[VIN] VIN event acknowledged by client (MID 0053).")

    def _handle_mid_0054(self, mid_int, rev, no_ack_flag, data_field, msg):
        if self.vin_subscribed:
            self.vin_subscribed = False
            resp = build_message(5, rev=1, data="0054")
            print("[VIN] Unsubscribed from VIN updates.")
        else:
            error_data = self._build_mid0004_data(1, 54, 7)
            resp = build_message(4, rev=1, data=error_data)
        self.send_to_client(resp)
    # === Tightening Result MID Handlers ===

    def _handle_mid_0060(self, mid_int, rev, no_ack_flag, data_field, msg):
        req_rev = int(rev) if rev.strip() else 1
        if self.result_subscribed:
            error_data = self._build_mid0004_data(1, 60, 9)
            resp = build_message(4, rev=1, data=error_data)
        else:
            subscribed_rev = self._get_response_revision(61, req_rev)
            self.result_subscribed_rev = subscribed_rev
            self.result_subscribed = True
            self.result_no_ack = (no_ack_flag == "1")
            resp = build_message(5, rev=1, data="0060")
            print(f"[Tightening] Subscribed at revision {subscribed_rev}.")
        self.send_to_client(resp)

    def _handle_mid_0062(self, mid_int, rev, no_ack_flag, data_field, msg):
        print("[Tightening] Tightening result acknowledged by client (MID 0062).")

    def _handle_mid_0063(self, mid_int, rev, no_ack_flag, data_field, msg):
        if self.result_subscribed:
            self.result_subscribed = False
            resp = build_message(5, rev=1, data="0063")
            print("[Tightening] Unsubscribed from tightening results.")
        else:
            error_data = self._build_mid0004_data(1, 63, 10)
            resp = build_message(4, rev=1, data=error_data)
        self.send_to_client(resp)

    # === Time MID Handlers ===

    def _handle_mid_0082(self, mid_int: int, rev: str, no_ack_flag: str, data_field: str, msg: bytes):
        time_str = data_field.strip()
        if len(time_str) == 19:
            try:
                datetime.datetime.strptime(time_str, "%Y-%m-%d:%H:%M:%S")
                self.controller_time = time_str
                resp = build_message(5, rev=1, data="0082")
                print(f"[Time] Controller time set to: {time_str}")
            except ValueError:
                error_data = self._build_mid0004_data(1, 82, 20)
                resp = build_message(4, rev=1, data=error_data)
                print(f"[Time] Invalid time format received: {time_str}")
        else:
            error_data = self._build_mid0004_data(1, 82, 20)
            resp = build_message(4, rev=1, data=error_data)
            print(f"[Time] Invalid time length received: {len(time_str)} chars (expected 19)")
        self.send_to_client(resp)

    # === Multi-spindle MID Handlers ===

    def _handle_mid_0100(self, mid_int: int, rev: str, no_ack_flag: str, data_field: str, msg: bytes):
        """MID 0100: Multi-spindle result subscribe (Rev 1-5)."""
        req_rev = int(rev.strip()) if rev.strip() else 1

        if req_rev > self.MAX_REV_0101:
            error_data = self._build_mid0004_data(1, 100, 97)
            resp = build_message(4, rev=1, data=error_data)
            print(f"[MultiSpindle] Revision {req_rev} not supported (max: {self.MAX_REV_0101}).")
        elif self.multi_spindle_subscribed:
            error_data = self._build_mid0004_data(1, 100, 9)
            resp = build_message(4, rev=1, data=error_data)
            print("[MultiSpindle] Subscribe failed: already subscribed.")
        else:
            self.multi_spindle_subscribed = True
            self.multi_spindle_no_ack = (no_ack_flag == "1")
            self.multi_spindle_requested_rev = req_rev

            if req_rev >= 2 and len(data_field) >= 10:
                rewind_point = data_field[:10]
                print(f"[MultiSpindle] Rewind point requested: {rewind_point} (ignored, emulator sends new only)")
            if req_rev >= 3 and len(data_field) >= 11:
                send_only_new = data_field[10:11]
                print(f"[MultiSpindle] Send only new flag: {send_only_new}")

            resp = build_message(5, rev=1, data="0100")
            print(f"[MultiSpindle] Subscription accepted (revision {req_rev}).")

        self.send_to_client(resp)

    def _initialize_default_pset_parameters(self):
        """Initializes default parameters for available Psets."""
        default_params = {
            "batch_size": 5,
            "target_torque": 50.00,
            "torque_min": 47.00,
            "torque_max": 53.00,
            "target_angle": 90,
            "angle_min": 80,
            "angle_max": 100,
        }
        for pset_id in self.available_psets:
            if pset_id not in self.pset_parameters: # Only initialize if not loaded from file
                self.pset_parameters[pset_id] = default_params.copy()
        print("[Pset Params] Initialized default Pset parameters for new Psets.")


    def _get_pset_filename(self, controller_name):
        """Generates the filename for Pset parameters based on controller name."""
        # Sanitize the controller name to be safe for filenames
        safe_name = re.sub(r'[^\w.-]', '_', controller_name)
        return f"pset_parameters_{safe_name}.json"


    def _load_pset_parameters(self, controller_name):
        """Loads Pset parameters from a JSON file based on controller name."""
        import json
        filename = self._get_pset_filename(controller_name)
        try:
            with open(filename, 'r') as f:
                self.pset_parameters = json.load(f)
            print(f"[Pset Params] Loaded parameters from {filename}")
            # Ensure all available_psets are in the loaded parameters, add defaults if missing
            self._initialize_default_pset_parameters()
        except FileNotFoundError:
            print(f"[Pset Params] No parameter file found ({filename}). Initializing defaults.")
            self._initialize_default_pset_parameters()
        except json.JSONDecodeError:
            print(f"[Pset Params] Error decoding JSON from {filename}. Initializing defaults.")
            self._initialize_default_pset_parameters()
        except Exception as e:
            print(f"[Pset Params] Unexpected error loading parameters: {e}. Initializing defaults.")
            self._initialize_default_pset_parameters()


    def _save_pset_parameters(self, controller_name):
        """Saves current Pset parameters to a JSON file based on controller name."""
        import json
        filename = self._get_pset_filename(controller_name)
        try:
            with open(filename, 'w') as f:
                json.dump(self.pset_parameters, f, indent=4)
            print(f"[Pset Params] Saved parameters to {filename}")
        except Exception as e:
            print(f"[Pset Params] Error saving parameters to {filename}: {e}")


    def _build_mid0015_data(self, revision: int) -> str:
        """Build MID 0015 Pset selected data for given revision (1-2)."""
        pset_id = (self.current_pset if self.current_pset else "0").rjust(3, '0')
        date_str = self.pset_last_change.strftime("%Y-%m-%d:%H:%M:%S") if self.pset_last_change else datetime.datetime.now().strftime("%Y-%m-%d:%H:%M:%S")

        if revision == 1:
            return pset_id + date_str

        elif revision >= 2:
            pset_params = self.pset_parameters.get(self.current_pset, {})
            batch_size = pset_params.get("batch_size", self.target_batch_size)
            with self.state_lock:
                batch_counter = self.batch_counter
                ok_counter = self.pset_ok_counter

            fields = []
            fields.append(f"01{pset_id}")
            fields.append(f"02{date_str}")
            fields.append(f"03{batch_size:04d}")
            fields.append(f"04{batch_counter:04d}")
            fields.append(f"05{ok_counter:04d}")
            return "".join(fields)

        return pset_id + date_str

    def _build_mid0041_data(self, revision: int) -> str:
        """Build MID 0041 Tool Data response for given revision (1-5)."""
        fields = []

        fields.append(f"01{self.tool_serial_number.ljust(14)[:14]}")
        fields.append(f"02{self.tool_number_of_tightenings:010d}")
        fields.append(f"03{self.tool_last_calib_date}")
        fields.append(f"04{self.tool_controller_serial}")

        if revision >= 2:
            fields.append(f"05{self.tool_calib_value:06d}")
            fields.append(f"06{self.tool_last_service_date}")
            fields.append(f"07{self.tool_tightenings_since_service:010d}")

        if revision >= 3:
            fields.append(f"08{self.tool_type:02d}")
            fields.append(f"09{self.tool_motor_size:04d}")

        if revision >= 4:
            fields.append(f"10{self.tool_open_end_data}")

        if revision >= 5:
            fields.append(f"11{self.tool_controller_software_version}")

        return "".join(fields)

    def _build_mid0052_data(self, revision: int) -> str:
        """Build MID 0052 VIN data for given revision (1-2)."""
        if revision == 1:
            return self.current_vin.ljust(25)[:25]

        elif revision >= 2:
            fields = []
            fields.append(f"01{self.current_vin.ljust(25)[:25]}")
            fields.append(f"02{self.identifier_part2.ljust(25)[:25]}")
            fields.append(f"03{self.identifier_part3.ljust(25)[:25]}")
            fields.append(f"04{self.identifier_part4.ljust(25)[:25]}")
            return "".join(fields)

        return self.current_vin.ljust(25)[:25]

    def _build_mid0061_data(self, revision: int, result_params: dict) -> str:
        """Build MID 0061 tightening result data for given revision (1-7)."""
        fields = []

        fields.append(f"01{result_params['cell_id']:04d}")
        fields.append(f"02{result_params['channel_id']:02d}")
        fields.append(f"03{result_params['controller_name']}")
        fields.append(f"04{result_params['vin']}")
        fields.append(f"05{result_params['job_id']:02d}")
        fields.append(f"06{result_params['pset_id']}")
        fields.append(f"07{result_params['batch_size']:04d}")
        fields.append(f"08{result_params['batch_counter']:04d}")
        fields.append(f"09{result_params['status']}")
        fields.append(f"10{result_params['torque_status']}")
        fields.append(f"11{result_params['angle_status']}")
        fields.append(f"12{result_params['torque_min']:06d}")
        fields.append(f"13{result_params['torque_max']:06d}")
        fields.append(f"14{result_params['torque_target']:06d}")
        fields.append(f"15{result_params['torque_final']:06d}")
        fields.append(f"16{result_params['angle_min']:05d}")
        fields.append(f"17{result_params['angle_max']:05d}")
        fields.append(f"18{result_params['angle_target']:05d}")
        fields.append(f"19{result_params['angle_final']:05d}")
        fields.append(f"20{result_params['timestamp']}")
        fields.append(f"21{result_params['pset_change_time']}")
        fields.append(f"22{result_params['batch_status']}")
        fields.append(f"23{result_params['tightening_id']:010d}")

        if revision >= 3:
            fields.append(f"24{self.strategy_code:04d}")

        if revision >= 4:
            fields.append(f"25{self.strategy_options}")

        if revision >= 5:
            fields.append(f"26{self.tightening_error_status_2:010d}")

        if revision >= 6:
            fields.append(f"27{self.stage_result_count:02d}")

        return "".join(fields)

    def _parse_vin(self, vin_string):
        """Parses VIN into prefix and numeric parts."""
        match = re.match(r'^(.*?)(\d+)$', vin_string)
        if match:
            self.vin_prefix = match.group(1)
            self.vin_numeric_str = match.group(2)
            self.vin_padding = len(self.vin_numeric_str)
            print(f"[VIN Parse] Parsed: Prefix='{self.vin_prefix}', Numeric='{self.vin_numeric_str}', Padding={self.vin_padding}")
            return True
        else:
            print(f"[VIN Parse] Error: Could not parse VIN '{vin_string}'. Using defaults.")
            self.vin_prefix = vin_string
            self.vin_numeric_str = "0"
            self.vin_padding = 1
            self.current_vin = vin_string + "0"
            return False

    def _increment_vin(self):
        """Increments the numeric part of the VIN and updates the state."""
        try:
            numeric_val = int(self.vin_numeric_str)
            numeric_val += 1
            self.vin_numeric_str = str(numeric_val).zfill(self.vin_padding)
            self.current_vin = self.vin_prefix + self.vin_numeric_str
            print(f"[VIN Increment] New VIN: {self.current_vin}")

            if self.vin_subscribed and self.session_active:
                vin_data = self._build_mid0052_data(self.vin_subscribed_rev)
                vin_msg = build_message(52, rev=self.vin_subscribed_rev, data=vin_data, no_ack=self.vin_no_ack)
                threading.Thread(target=self.send_to_client, args=(vin_msg,), daemon=True).start()
                print(f"[VIN] Sent VIN update event (MID 0052 rev {self.vin_subscribed_rev}): {self.current_vin}")

        except ValueError:
            print("[VIN Increment] Error: Could not increment VIN numeric part.")

    def start_server(self):
        """Start the TCP server to accept connections."""
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Bind using the configured port
        try:
            server_sock.bind((self.host, self.port))
        except OSError as e:
             print(f"[Server Error] Failed to bind to port {self.port}: {e}")
             print("Check if another application is using the port.")
             return # Exit if cannot bind
        server_sock.listen(1)
        print(f"[Server] Listening on {self.host}:{self.port} with name '{self.controller_name.strip()}'...")
        while True:
            try:
                client_sock, addr = server_sock.accept()
            except OSError:
                print("[Server] Error accepting connection (server socket closed?).")
                break # Exit loop if server socket has issues

            if self.session_active:
                print(f"[Server] Rejecting connection from {addr}: already connected.")
                error_data = self._build_mid0004_data(1, 1, 96)
                err_msg = build_message(4, rev=1, data=error_data)
                try: client_sock.sendall(err_msg)
                except (OSError, BrokenPipeError): pass
                client_sock.close()
                continue

            self.tightening_id_counter = 0
            with self.state_lock:
                self.batch_counter = 0
            self.tool_enabled = True
            self.auto_send_loop_active = True
            print(f"[Server] New client connected from {addr}, resetting counters and enabling tool/loop.")
            threading.Thread(target=self.handle_client, args=(client_sock, addr), daemon=True).start()

    def send_to_client(self, msg_bytes: bytes):
        """Thread-safe send to the client."""
        if self.client_socket:
            with self.send_lock:
                try:
                    self.client_socket.sendall(msg_bytes)
                    log_msg = msg_bytes.decode('ascii', errors='ignore').replace('\x00', '')
                    print(f"[Send] MID {log_msg[4:8]} ({len(msg_bytes)} bytes): {log_msg[20:60]}...")
                except (OSError, BrokenPipeError, ConnectionResetError) as e:
                    print(f"[Send Error] Connection issue: {e}")
                    try: self.client_socket.close()
                    except OSError: pass
                    self.client_socket = None
                    self.session_active = False # Ensure session ends on error
                except Exception as e:
                    print(f"[Send Error] Unexpected error: {e}")
                    try: self.client_socket.close()
                    except OSError: pass
                    self.client_socket = None
                    self.session_active = False

    def handle_client(self, sock: socket.socket, addr):
        """Handle messages from a connected client."""
        self.client_socket = sock
        print(f"[Client] Connection established with {addr}")
        buffer = b""
        while True:
            try: data = sock.recv(1024)
            except (ConnectionResetError, OSError) as e: print(f"[Recv Error] Connection issue: {e}"); break
            except Exception as e: print(f"[Recv Error] Unexpected error: {e}"); break
            if not data: print("[Client] Connection closed by peer."); break
            buffer += data
            while True:
                if len(buffer) < 4: break
                try: length = int(buffer[:4].decode('ascii'))
                except ValueError: print("[Error] Invalid length field"); buffer = b""; break
                if len(buffer) < length + 1: break

                full_msg = buffer[:length+1]
                log_msg_recv = full_msg.decode('ascii', errors='ignore').replace('\x00', '')
                print(f"[Recv] MID {log_msg_recv[4:8]} ({len(full_msg)} bytes): {log_msg_recv[20:60]}...")
                buffer = buffer[length+1:]
                self.process_message(full_msg)

        print(f"[Client] Cleaning up connection from {addr}.")
        self.session_active = False
        self.vin_subscribed = False; self.result_subscribed = False; self.pset_subscribed = False
        self.pset_subscribed_rev = 1
        self.vin_subscribed_rev = 1
        self.result_subscribed_rev = 1
        try: sock.close()
        except OSError: pass
        self.client_socket = None

    def process_message(self, msg: bytes):
        """Parse and dispatch an Open Protocol message."""
        if len(msg) < 21:
            print(f"[Error] Malformed message (too short): {msg}")
            return
        try:
            mid = msg[4:8].decode('ascii')
            rev = msg[8:11].decode('ascii')
            no_ack_flag = msg[11:12].decode('ascii')
            data_field = msg[20:-1].decode('ascii')
            mid_int = int(mid)
        except (ValueError, IndexError, UnicodeDecodeError) as e:
            print(f"[Error] Parse error: {e}, Message: {msg}")
            return

        # --- MID Dispatch via Registry ---
        handler = self.mid_handlers.get(mid_int)
        if handler:
            handler(mid_int, rev, no_ack_flag, data_field, msg)
        else:
            error_data = self._build_mid0004_data(1, mid_int, 99)
            resp = build_message(4, rev=1, data=error_data)
            self.send_to_client(resp)
            print(f"[Unknown] Received unsupported MID {mid}. Sent error.")


    def send_single_tightening_result(self):
        """Generate and send a single simulated MID 0061 tightening result."""
        if not self.tool_enabled:
            print("[Tightening] Send prevented: Tool is disabled (MID 0042/0040).")
            return
        if not self.session_active or not self.result_subscribed:
            print("[Tightening] Send prevented: Session inactive or not subscribed.")
            return

        self.tightening_id_counter = (self.tightening_id_counter + 1) % 10000000000

        tighten_time = datetime.datetime.now()
        timestamp_str = tighten_time.strftime("%Y-%m-%d:%H:%M:%S")
        pset_change_ts = (self.pset_last_change.strftime("%Y-%m-%d:%H:%M:%S")
                          if self.pset_last_change else timestamp_str)

        current_pset_params = self.pset_parameters.get(self.current_pset)

        if current_pset_params:
            target_torque = current_pset_params["target_torque"]
            torque_min = current_pset_params["torque_min"]
            torque_max = current_pset_params["torque_max"]
            target_angle = current_pset_params["target_angle"]
            angle_min = current_pset_params["angle_min"]
            angle_max = current_pset_params["angle_max"]
            current_target_batch_size = current_pset_params["batch_size"]
            print(f"[Tightening] Using parameters from Pset {self.current_pset}")
        else:
            target_torque = 50.00
            torque_min = 47.00
            torque_max = 53.00
            target_angle = 90
            angle_min = 80
            angle_max = 100
            current_target_batch_size = self.target_batch_size
            print("[Tightening] Using global default parameters.")

        is_nok = random.random() < self.nok_probability
        status = "0" if is_nok else "1"
        torque_status = "1"
        angle_status = "1"
        actual_torque = random.uniform(torque_min, torque_max)
        actual_angle = random.uniform(angle_min, angle_max)

        if is_nok:
            if random.choice(["torque", "angle"]) == "torque":
                torque_status = random.choice(["0", "2"])
                actual_torque = random.uniform(torque_min - 5, torque_min - 0.1) if torque_status == "0" else random.uniform(torque_max + 0.1, torque_max + 5)
            else:
                angle_status = random.choice(["0", "2"])
                actual_angle = random.uniform(angle_min - 20, angle_min - 1) if angle_status == "0" else random.uniform(angle_max + 1, angle_max + 20)

        with self.state_lock:
            self.tool_number_of_tightenings += 1
            self.tool_tightenings_since_service += 1

            if status == "1":
                self.pset_ok_counter += 1
                if current_target_batch_size > 0:
                    self.batch_counter += 1
                    print(f"[Batch] Counter incremented to {self.batch_counter}/{current_target_batch_size}")

            batch_counter_val = self.batch_counter
            if current_target_batch_size == 0:
                batch_status = "0"
                batch_completed = False
            elif batch_counter_val < current_target_batch_size:
                batch_status = "0"
                batch_completed = False
            else:
                batch_status = "1"
                batch_completed = True

        result_params = {
            'cell_id': 1,
            'channel_id': 1,
            'controller_name': self.controller_name,
            'vin': self.current_vin.ljust(25)[:25],
            'job_id': 0,
            'pset_id': (self.current_pset if self.current_pset else "0").rjust(3, '0'),
            'batch_size': current_target_batch_size,
            'batch_counter': batch_counter_val,
            'status': status,
            'torque_status': torque_status,
            'angle_status': angle_status,
            'torque_min': int(torque_min * 100),
            'torque_max': int(torque_max * 100),
            'torque_target': int(target_torque * 100),
            'torque_final': int(actual_torque * 100),
            'angle_min': int(angle_min),
            'angle_max': int(angle_max),
            'angle_target': int(target_angle),
            'angle_final': int(actual_angle),
            'timestamp': timestamp_str,
            'pset_change_time': pset_change_ts,
            'batch_status': batch_status,
            'tightening_id': self.tightening_id_counter,
        }

        data = self._build_mid0061_data(self.result_subscribed_rev, result_params)
        result_msg = build_message(61, rev=self.result_subscribed_rev, data=data, no_ack=self.result_no_ack)
        self.send_to_client(result_msg)
        print(f"[Tightening] Sent result (MID 0061 rev {self.result_subscribed_rev}, ID: {self.tightening_id_counter:010d}). Status: {'OK' if status == '1' else 'NOK'}, Batch: {batch_counter_val}/{current_target_batch_size}")

        if batch_completed:
            print("[Batch] Batch complete!")
            self._increment_vin()
            with self.state_lock:
                self.batch_counter = 0
            print("[Batch] VIN incremented and counter reset.")


    def send_tightening_results_loop(self):
        """Periodically send a simulated MID 0061 tightening result."""
        while self.session_active:
            # Use the configurable interval
            for _ in range(self.auto_loop_interval):
                if not self.session_active: print("[Auto Loop] Session ended."); return
                time.sleep(1)

            # Check if loop is active AND tool is enabled by protocol
            if self.session_active and self.result_subscribed and self.auto_send_loop_active:
                 # The check for self.tool_enabled is now inside send_single_tightening_result
                 self.send_single_tightening_result()
            elif not self.session_active: print("[Auto Loop] Session ended during wait."); return


    def start_gui(self):
        """Start a simple Tkinter GUI with VIN, Batch, and Tool controls."""
        # Use configured name and port in title
        window_title = f"{self.controller_name.strip()} (Port: {self.port})"
        root = tk.Tk()
        root.title(window_title)

        # --- GUI Variables ---
        vin_var = tk.StringVar(value=self.current_vin)
        batch_size_var = tk.StringVar(value=str(self.target_batch_size))
        nok_prob_var = tk.StringVar(value=str(int(self.nok_probability * 100)))
        auto_loop_interval_var = tk.StringVar(value=str(self.auto_loop_interval)) # New variable for interval
        auto_send_loop_status_var = tk.StringVar(value="Active")
        pset_display_var = tk.StringVar(value="Pset: Not set")
        conn_display_var = tk.StringVar(value="Status: Disconnected")
        batch_display_var = tk.StringVar(value=f"Batch: {self.batch_counter}/{self.target_batch_size}")
        vin_display_var = tk.StringVar(value=f"VIN: {self.current_vin}")
        tool_protocol_status_var = tk.StringVar(value="Tool Status: Enabled")
        # --- End GUI Variables ---

        # --- Pset GUI Variables ---
        pset_id_var = tk.StringVar(value=list(self.available_psets)[0] if self.available_psets else "")
        pset_batch_size_var = tk.StringVar(value="")
        pset_target_torque_var = tk.StringVar(value="")
        pset_torque_min_var = tk.StringVar(value="")
        pset_torque_max_var = tk.StringVar(value="")
        pset_target_angle_var = tk.StringVar(value="")
        pset_angle_min_var = tk.StringVar(value="")
        pset_angle_max_var = tk.StringVar(value="")
        # --- End Pset GUI Variables ---


        # --- GUI Callbacks ---
        def apply_global_settings():
            try:
                new_vin = vin_var.get()
                if new_vin != self.current_vin:
                    if self._parse_vin(new_vin):
                        self.current_vin = new_vin
                        with self.state_lock:
                            self.batch_counter = 0
                        print(f"[GUI Apply] VIN set to {self.current_vin}, batch counter reset.")
                    else:
                        messagebox.showerror("Error", f"Invalid VIN format: {new_vin}")
                        vin_var.set(self.current_vin)

                # Global batch size is now less relevant, but keep for fallback or other uses
                new_batch_size = int(batch_size_var.get())
                if new_batch_size >= 0:
                    self.target_batch_size = new_batch_size
                    print(f"[GUI Apply] Global Batch Size set to {self.target_batch_size}.")
                else: messagebox.showerror("Error", "Batch Size must be >= 0"); batch_size_var.set(str(self.target_batch_size))


                new_nok_prob_pct = int(nok_prob_var.get())
                if 0 <= new_nok_prob_pct <= 100:
                    self.nok_probability = new_nok_prob_pct / 100.0
                    print(f"[GUI Apply] NOK Probability set to {self.nok_probability:.2f}")
                else: messagebox.showerror("Error", "NOK % must be 0-100"); nok_prob_var.set(str(int(self.nok_probability * 100)))

                new_interval = int(auto_loop_interval_var.get()) # Read new interval
                if new_interval > 0:
                    self.auto_loop_interval = new_interval
                    print(f"[GUI Apply] Auto Loop Interval set to {self.auto_loop_interval} seconds.")
                else: messagebox.showerror("Error", "Interval must be > 0"); auto_loop_interval_var.set(str(self.auto_loop_interval))

                update_labels()
            except ValueError:
                messagebox.showerror("Error", "Invalid number format for Batch Size, NOK %, or Interval.")
                batch_size_var.set(str(self.target_batch_size)); nok_prob_var.set(str(int(self.nok_probability * 100)))
                auto_loop_interval_var.set(str(self.auto_loop_interval))

        def load_pset_settings():
            selected_pset = pset_id_var.get()
            if selected_pset in self.pset_parameters:
                params = self.pset_parameters[selected_pset]
                pset_batch_size_var.set(str(params["batch_size"]))
                pset_target_torque_var.set(str(params["target_torque"]))
                pset_torque_min_var.set(str(params["torque_min"]))
                pset_torque_max_var.set(str(params["torque_max"]))
                pset_target_angle_var.set(str(params["target_angle"]))
                pset_angle_min_var.set(str(params["angle_min"]))
                pset_angle_max_var.set(str(params["angle_max"]))
                print(f"[GUI] Loaded settings for Pset {selected_pset}")
            else:
                messagebox.showwarning("Warning", f"Pset {selected_pset} not found or no parameters initialized.")
                # Clear fields if Pset not found
                pset_batch_size_var.set("")
                pset_target_torque_var.set("")
                pset_torque_min_var.set("")
                pset_torque_max_var.set("")
                pset_target_angle_var.set("")
                pset_angle_min_var.set("")
                pset_angle_max_var.set("")


        def apply_pset_settings():
            selected_pset = pset_id_var.get()
            if selected_pset not in self.available_psets:
                 messagebox.showerror("Error", f"Invalid Pset ID: {selected_pset}"); return

            try:
                new_params = {
                    "batch_size": int(pset_batch_size_var.get()),
                    "target_torque": float(pset_target_torque_var.get()),
                    "torque_min": float(pset_torque_min_var.get()),
                    "torque_max": float(pset_torque_max_var.get()),
                    "target_angle": int(pset_target_angle_var.get()),
                    "angle_min": int(pset_angle_min_var.get()),
                    "angle_max": int(pset_angle_max_var.get()),
                }
                # Basic validation (can add more specific checks)
                if new_params["batch_size"] < 0: raise ValueError("Batch size must be >= 0")
                if new_params["torque_min"] > new_params["torque_max"]: raise ValueError("Min Torque > Max Torque")
                if new_params["angle_min"] > new_params["angle_max"]: raise ValueError("Min Angle > Max Angle")


                self.pset_parameters[selected_pset] = new_params
                print(f"[GUI] Applied settings for Pset {selected_pset}: {new_params}")
                self._save_pset_parameters(self.controller_name) # Save immediately after applying, passing controller name
                messagebox.showinfo("Success", f"Settings applied for Pset {selected_pset}")

            except ValueError as e:
                messagebox.showerror("Error", f"Invalid number format or value: {e}")
            except Exception as e:
                messagebox.showerror("Error", f"An unexpected error occurred: {e}")


        def toggle_auto_send_loop():
            self.auto_send_loop_active = not self.auto_send_loop_active
            new_status = "Active" if self.auto_send_loop_active else "Paused"
            auto_send_loop_status_var.set(new_status)
            print(f"[GUI] Auto-send loop {new_status}")

        def manual_send_result():
            print("[GUI] Manual send triggered.")
            threading.Thread(target=self.send_single_tightening_result, daemon=True).start()

        def update_labels():
            pset_display_var.set("Pset: " + (self.current_pset if self.current_pset else "Not set"))
            conn_display_var.set("Status: " + ("Connected" if self.session_active else "Disconnected"))
            current_target_batch = self.pset_parameters.get(self.current_pset, {}).get("batch_size", self.target_batch_size)
            with self.state_lock:
                current_batch = self.batch_counter
            batch_display_var.set(f"Batch: {current_batch}/{current_target_batch}")

            vin_display_var.set(f"VIN: {self.current_vin}")
            tool_protocol_status_var.set("Tool Status: " + ("Enabled" if self.tool_enabled else "Disabled"))
            try: root.after(1000, update_labels)
            except tk.TclError: pass
        # --- End GUI Callbacks ---

        # --- GUI Layout ---
        settings_frame = tk.LabelFrame(root, text="Global Settings", padx=5, pady=5)
        settings_frame.pack(padx=10, pady=5, fill=tk.X)
        tk.Label(settings_frame, text="Initial VIN:").grid(row=0, column=0, sticky=tk.W, padx=2, pady=2)
        tk.Entry(settings_frame, textvariable=vin_var, width=20).grid(row=0, column=1, sticky=tk.W, padx=2, pady=2)
        tk.Label(settings_frame, text="Global Batch Size:").grid(row=1, column=0, sticky=tk.W, padx=2, pady=2) # Renamed label
        tk.Entry(settings_frame, textvariable=batch_size_var, width=5).grid(row=1, column=1, sticky=tk.W, padx=2, pady=2)
        tk.Label(settings_frame, text="NOK %:").grid(row=2, column=0, sticky=tk.W, padx=2, pady=2)
        tk.Entry(settings_frame, textvariable=nok_prob_var, width=5).grid(row=2, column=1, sticky=tk.W, padx=2, pady=2)
        tk.Label(settings_frame, text="Auto Loop Interval (s):").grid(row=3, column=0, sticky=tk.W, padx=2, pady=2)
        tk.Entry(settings_frame, textvariable=auto_loop_interval_var, width=5).grid(row=3, column=1, sticky=tk.W, pady=2)
        tk.Button(settings_frame, text="Apply Global Settings", command=apply_global_settings).grid(row=0, column=2, rowspan=4, padx=10, pady=2, sticky=tk.NS) # Renamed button and command

        # --- Pset Settings Frame ---
        pset_settings_frame = tk.LabelFrame(root, text="Pset Settings", padx=5, pady=5)
        pset_settings_frame.pack(padx=10, pady=5, fill=tk.X)

        tk.Label(pset_settings_frame, text="Pset ID:").grid(row=0, column=0, sticky=tk.W, padx=2, pady=2)
        # Using OptionMenu for Pset selection
        pset_id_optionmenu = tk.OptionMenu(pset_settings_frame, pset_id_var, *sorted(list(self.available_psets)))
        pset_id_optionmenu.grid(row=0, column=1, sticky=tk.W, padx=2, pady=2)
        tk.Button(pset_settings_frame, text="Load Pset Settings", command=load_pset_settings).grid(row=0, column=2, padx=10, pady=2)


        tk.Label(pset_settings_frame, text="Batch Size:").grid(row=1, column=0, sticky=tk.W, padx=2, pady=2)
        tk.Entry(pset_settings_frame, textvariable=pset_batch_size_var, width=5).grid(row=1, column=1, sticky=tk.W, padx=2, pady=2)

        tk.Label(pset_settings_frame, text="Target Torque:").grid(row=2, column=0, sticky=tk.W, padx=2, pady=2)
        tk.Entry(pset_settings_frame, textvariable=pset_target_torque_var, width=8).grid(row=2, column=1, sticky=tk.W, padx=2, pady=2)
        tk.Label(pset_settings_frame, text="Min Torque:").grid(row=2, column=2, sticky=tk.W, padx=2, pady=2)
        tk.Entry(pset_settings_frame, textvariable=pset_torque_min_var, width=8).grid(row=2, column=3, sticky=tk.W, padx=2, pady=2)
        tk.Label(pset_settings_frame, text="Max Torque:").grid(row=2, column=4, sticky=tk.W, padx=2, pady=2)
        tk.Entry(pset_settings_frame, textvariable=pset_torque_max_var, width=8).grid(row=2, column=5, sticky=tk.W, padx=2, pady=2)

        tk.Label(pset_settings_frame, text="Target Angle:").grid(row=3, column=0, sticky=tk.W, padx=2, pady=2)
        tk.Entry(pset_settings_frame, textvariable=pset_target_angle_var, width=5).grid(row=3, column=1, sticky=tk.W, padx=2, pady=2)
        tk.Label(pset_settings_frame, text="Min Angle:").grid(row=3, column=2, sticky=tk.W, padx=2, pady=2)
        tk.Entry(pset_settings_frame, textvariable=pset_angle_min_var, width=5).grid(row=3, column=3, sticky=tk.W, padx=2, pady=2)
        tk.Label(pset_settings_frame, text="Max Angle:").grid(row=3, column=4, sticky=tk.W, padx=2, pady=2)
        tk.Entry(pset_settings_frame, textvariable=pset_angle_max_var, width=5).grid(row=3, column=5, sticky=tk.W, padx=2, pady=2)

        tk.Button(pset_settings_frame, text="Apply Pset Settings", command=apply_pset_settings).grid(row=1, column=6, rowspan=3, padx=10, pady=2, sticky=tk.NS) # Adjusted rowspan and column

        # --- End Pset Settings Frame ---


        control_frame = tk.LabelFrame(root, text="Controls", padx=5, pady=5)
        control_frame.pack(padx=10, pady=5, fill=tk.X)
        toggle_loop_btn = tk.Button(control_frame, text="Toggle Auto Loop", command=toggle_auto_send_loop)
        toggle_loop_btn.pack(side=tk.LEFT, padx=5)
        auto_send_label = tk.Label(control_frame, textvariable=auto_send_loop_status_var, relief=tk.SUNKEN, width=10)
        auto_send_label.pack(side=tk.LEFT, padx=5)
        tk.Button(control_frame, text="Send Single Result", command=manual_send_result).pack(side=tk.LEFT, padx=10)

        status_frame = tk.LabelFrame(root, text="Status", padx=5, pady=5)
        status_frame.pack(padx=10, pady=10, fill=tk.X)
        tk.Label(status_frame, textvariable=conn_display_var).pack(anchor=tk.W)
        tk.Label(status_frame, textvariable=tool_protocol_status_var).pack(anchor=tk.W)
        tk.Label(status_frame, textvariable=pset_display_var).pack(anchor=tk.W)
        tk.Label(status_frame, textvariable=vin_display_var).pack(anchor=tk.W)
        tk.Label(status_frame, textvariable=batch_display_var).pack(anchor=tk.W)
        # --- End GUI Layout ---

        # Bind the save function to the window closing event
        root.protocol("WM_DELETE_WINDOW", lambda: (self._save_pset_parameters(self.controller_name), root.destroy()))

        # Bind load_pset_settings to the Pset ID variable trace
        pset_id_var.trace_add("write", lambda name, index, mode: load_pset_settings())

        # Load initial Pset settings into GUI fields
        load_pset_settings()

        update_labels()
        root.mainloop()

# Main entry point
if __name__ == "__main__":
    # Setup argument parser
    parser = argparse.ArgumentParser(description="Open Protocol Emulator")
    parser.add_argument("-p", "--port", type=int, default=4545,
                        help="Port number to listen on (default: 4545)")
    parser.add_argument("-n", "--name", type=str, default="OpenProtocolSim",
                        help="Controller name reported in MID 0002 (default: OpenProtocolSim)")
    args = parser.parse_args()

    # Create and run emulator instance with arguments
    emulator = OpenProtocolEmulator(port=args.port, controller_name=args.name)
    server_thread = threading.Thread(target=emulator.start_server, daemon=True)
    server_thread.start()

    # Start GUI only if server thread started successfully (basic check)
    if server_thread.is_alive():
        try:
            emulator.start_gui() # Runs in main thread
        except tk.TclError as e:
             print(f"[GUI Error] Failed to start Tkinter GUI: {e}")
             print("Ensure a display environment is available.")
        except Exception as e:
             print(f"[GUI Error] Unexpected error starting GUI: {e}")
    else:
        print("[Error] Server thread failed to start. Exiting.")
