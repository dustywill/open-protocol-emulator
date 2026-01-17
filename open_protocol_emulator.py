#!/usr/bin/env python3
import socket
import threading
import time
import datetime
import random
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import re
import argparse
import os
import json

CONTROLLERS_DIR = "controllers"

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
    DEFAULT_PROFILES = {
        "legacy": {
            "description": "Legacy mode - revision 1 only for all MIDs",
            "revisions": {
                2: 1, 4: 1, 15: 1, 41: 1, 52: 1, 61: 1, 101: 1, 215: 1
            }
        },
        "pf6000-basic": {
            "description": "PF6000 basic - moderate revision support",
            "revisions": {
                2: 3, 4: 2, 15: 1, 41: 2, 52: 1, 61: 2, 101: 2, 215: 1
            }
        },
        "pf6000-full": {
            "description": "PF6000 full - maximum revision support",
            "revisions": {
                2: 6, 4: 3, 15: 2, 41: 5, 52: 2, 61: 7, 101: 5, 215: 2
            }
        }
    }

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
        # --- I/O Device and Relay State ---
        self.io_devices = {
            "00": {
                "relays": [
                    {"function": 1, "status": 0},
                    {"function": 2, "status": 0},
                    {"function": 9, "status": 0},
                    {"function": 10, "status": 0},
                    {"function": 18, "status": 1},
                    {"function": 19, "status": 1},
                    {"function": 30, "status": 0},
                    {"function": 0, "status": 0},
                ],
                "digital_inputs": [
                    {"function": 0, "status": 0},
                    {"function": 0, "status": 0},
                    {"function": 0, "status": 0},
                    {"function": 0, "status": 0},
                    {"function": 0, "status": 0},
                    {"function": 0, "status": 0},
                    {"function": 0, "status": 0},
                    {"function": 0, "status": 0},
                ]
            }
        }
        self.relay_subscriptions = {}
        # --- End I/O Device and Relay State ---

        # --- Revision Configuration ---
        # Maps MID numbers to their maximum supported revision.
        # This enables runtime configuration of revision limits without code changes.
        self.revision_config = {
            2: 6,     # MID 0002 - Communication start ack
            4: 3,     # MID 0004 - Communication negative ack
            15: 2,    # MID 0015 - Pset selected
            41: 5,    # MID 0041 - Tool data reply
            52: 2,    # MID 0052 - VIN number
            61: 7,    # MID 0061 - Tightening result
            101: 5,   # MID 0101 - Multi-spindle result
            215: 2,   # MID 0215 - I/O device status reply
        }
        self.current_profile = "pf6000-full"  # Default profile name
        # --- End Revision Configuration ---
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
            100: self._handle_mid_0100,
            102: self._handle_mid_0102,
            103: self._handle_mid_0103,
            214: self._handle_mid_0214,
            216: self._handle_mid_0216,
            218: self._handle_mid_0218,
            219: self._handle_mid_0219,
        }

    def _get_response_revision(self, mid: int, requested_rev: int) -> int:
        """Return highest supported revision <= requested."""
        max_supported = self.revision_config.get(mid, 1)
        return min(requested_rev, max_supported)

    def get_max_revision(self, mid: int) -> int:
        """Get the maximum supported revision for a MID."""
        return self.revision_config.get(mid, 1)

    def set_max_revision(self, mid: int, max_rev: int) -> None:
        """Set the maximum supported revision for a MID."""
        if max_rev < 1:
            raise ValueError(f"Revision must be >= 1, got {max_rev}")
        self.revision_config[mid] = max_rev

    def get_all_revision_config(self) -> dict:
        """Get a copy of the full revision configuration."""
        return dict(self.revision_config)

    def apply_profile(self, profile_name: str) -> None:
        """Apply a controller profile by name (built-in or from controllers folder)."""
        if profile_name in self.DEFAULT_PROFILES:
            profile = self.DEFAULT_PROFILES[profile_name]
            self.revision_config.update(profile["revisions"])
            self.current_profile = profile_name
            return

        filepath = os.path.join(CONTROLLERS_DIR, f"{profile_name}.json")
        if os.path.exists(filepath):
            self.load_profile_from_file(filepath)
            return

        raise ValueError(f"Unknown profile: {profile_name}")

    def get_current_profile(self) -> str:
        """Get the name of the currently active profile."""
        return self.current_profile

    def get_available_profiles(self) -> list:
        """Get list of available profile names (built-in + controllers folder)."""
        profiles = list(self.DEFAULT_PROFILES.keys())
        if os.path.exists(CONTROLLERS_DIR):
            for filename in os.listdir(CONTROLLERS_DIR):
                if filename.endswith('.json'):
                    profile_name = filename[:-5]
                    if profile_name not in profiles:
                        profiles.append(profile_name)
        return profiles

    def get_profile_description(self, profile_name: str) -> str:
        """Get the description of a profile."""
        if profile_name in self.DEFAULT_PROFILES:
            return self.DEFAULT_PROFILES[profile_name]["description"]
        filepath = os.path.join(CONTROLLERS_DIR, f"{profile_name}.json")
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                profile_data = json.load(f)
            return profile_data.get("description", f"Custom profile: {profile_name}")
        return "Unknown profile"

    def save_profile_to_file(self, filepath: str, profile_name: str) -> None:
        """Save current revision config as a named profile to JSON file."""
        profile_data = {
            "name": profile_name,
            "description": f"Custom profile: {profile_name}",
            "revisions": dict(self.revision_config)
        }
        with open(filepath, 'w') as f:
            json.dump(profile_data, f, indent=2)

    def save_profile_to_controllers(self, profile_name: str) -> str:
        """Save current revision config to controllers folder. Returns filepath."""
        if not os.path.exists(CONTROLLERS_DIR):
            os.makedirs(CONTROLLERS_DIR)
        filepath = os.path.join(CONTROLLERS_DIR, f"{profile_name}.json")
        self.save_profile_to_file(filepath, profile_name)
        self.current_profile = profile_name
        return filepath

    def load_profile_from_file(self, filepath: str) -> str:
        """Load a profile from JSON file and apply it. Returns profile name."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Profile file not found: {filepath}")

        with open(filepath, 'r') as f:
            profile_data = json.load(f)

        if "revisions" not in profile_data:
            raise ValueError("Invalid profile file: missing 'revisions' key")

        for mid_str, rev in profile_data["revisions"].items():
            mid = int(mid_str)
            self.revision_config[mid] = rev

        profile_name = profile_data.get("name", "custom")
        self.current_profile = profile_name
        return profile_name

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

        if req_rev > self.revision_config.get(101, 1):
            error_data = self._build_mid0004_data(1, 100, 97)
            resp = build_message(4, rev=1, data=error_data)
            print(f"[MultiSpindle] Revision {req_rev} not supported (max: {self.revision_config.get(101, 1)}).")
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

    def _handle_mid_0102(self, mid_int: int, rev: str, no_ack_flag: str, data_field: str, msg: bytes):
        """MID 0102: Multi-spindle result acknowledge."""
        print("[MultiSpindle] Result acknowledged by client (MID 0102).")

    def _handle_mid_0103(self, mid_int: int, rev: str, no_ack_flag: str, data_field: str, msg: bytes):
        """MID 0103: Multi-spindle result unsubscribe."""
        if self.multi_spindle_subscribed:
            self.multi_spindle_subscribed = False
            self.multi_spindle_no_ack = False
            resp = build_message(5, rev=1, data="0103")
            print("[MultiSpindle] Unsubscribed from multi-spindle results.")
        else:
            error_data = self._build_mid0004_data(1, 103, 10)
            resp = build_message(4, rev=1, data=error_data)
            print("[MultiSpindle] Unsubscribe failed: not subscribed.")
        self.send_to_client(resp)

    # === I/O Device MID Handlers ===

    def _handle_mid_0214(self, mid_int: int, rev: str, no_ack_flag: str, data_field: str, msg: bytes):
        """MID 0214: I/O device status request (Rev 1-2)."""
        device_num = data_field[:2] if len(data_field) >= 2 else "00"
        req_rev = int(rev.strip()) if rev.strip() else 1

        if req_rev > self.revision_config.get(215, 1):
            error_data = self._build_mid0004_data(1, 214, 97)
            resp = build_message(4, rev=1, data=error_data)
            print(f"[IO] Revision {req_rev} not supported for MID 0214.")
        elif device_num not in self.io_devices:
            error_data = self._build_mid0004_data(1, 214, 1)
            resp = build_message(4, rev=1, data=error_data)
            print(f"[IO] Device {device_num} not found.")
        else:
            device = self.io_devices[device_num]
            relays = device["relays"]
            digital_inputs = device["digital_inputs"]

            if req_rev == 1:
                fields = []
                fields.append(f"01{device_num}")

                relay_data = ""
                for relay in relays[:8]:
                    relay_data += f"{relay['function']:03d}{relay['status']}"
                while len(relay_data) < 32:
                    relay_data += "0000"
                fields.append(f"02{relay_data}")

                din_data = ""
                for din in digital_inputs[:8]:
                    din_data += f"{din['function']:03d}{din['status']}"
                while len(din_data) < 32:
                    din_data += "0000"
                fields.append(f"03{din_data}")

                data = "".join(fields)
                resp = build_message(215, rev=1, data=data)

            else:
                fields = []
                fields.append(f"01{device_num}")
                fields.append(f"02{len(relays):02d}")

                relay_data = ""
                for relay in relays:
                    relay_data += f"{relay['function']:03d}{relay['status']}"
                fields.append(f"03{relay_data}")

                fields.append(f"04{len(digital_inputs):02d}")

                din_data = ""
                for din in digital_inputs:
                    din_data += f"{din['function']:03d}{din['status']}"
                fields.append(f"05{din_data}")

                data = "".join(fields)
                resp = build_message(215, rev=2, data=data)

            print(f"[IO] Sent device {device_num} status (MID 0215 rev {req_rev}).")

        self.send_to_client(resp)

    def _handle_mid_0216(self, mid_int: int, rev: str, no_ack_flag: str, data_field: str, msg: bytes):
        """MID 0216: Relay function subscribe."""
        relay_func = data_field[:3] if len(data_field) >= 3 else "000"

        try:
            relay_num = int(relay_func)
        except ValueError:
            error_data = self._build_mid0004_data(1, 216, 99)
            resp = build_message(4, rev=1, data=error_data)
            self.send_to_client(resp)
            return

        if relay_num in self.relay_subscriptions:
            error_data = self._build_mid0004_data(1, 216, 6)
            resp = build_message(4, rev=1, data=error_data)
            print(f"[Relay] Subscription for relay function {relay_num} already exists.")
        else:
            self.relay_subscriptions[relay_num] = (no_ack_flag == "1")
            resp = build_message(5, rev=1, data="0216")
            print(f"[Relay] Subscribed to relay function {relay_num}.")

            self.send_to_client(resp)
            self._send_relay_status(relay_num)
            return

        self.send_to_client(resp)

    def _handle_mid_0218(self, mid_int: int, rev: str, no_ack_flag: str, data_field: str, msg: bytes):
        """MID 0218: Relay function acknowledge."""
        print("[Relay] Relay function acknowledged by client (MID 0218).")

    def _handle_mid_0219(self, mid_int: int, rev: str, no_ack_flag: str, data_field: str, msg: bytes):
        """MID 0219: Relay function unsubscribe."""
        relay_func = data_field[:3] if len(data_field) >= 3 else "000"

        try:
            relay_num = int(relay_func)
        except ValueError:
            error_data = self._build_mid0004_data(1, 219, 99)
            resp = build_message(4, rev=1, data=error_data)
            self.send_to_client(resp)
            return

        if relay_num in self.relay_subscriptions:
            del self.relay_subscriptions[relay_num]
            resp = build_message(5, rev=1, data="0219")
            print(f"[Relay] Unsubscribed from relay function {relay_num}.")
        else:
            error_data = self._build_mid0004_data(1, 219, 7)
            resp = build_message(4, rev=1, data=error_data)
            print(f"[Relay] Unsubscribe failed: not subscribed to relay {relay_num}.")

        self.send_to_client(resp)

    def _send_relay_status(self, relay_func: int):
        """Send MID 0217 relay function status for a subscribed relay."""
        status = 0
        for device in self.io_devices.values():
            for relay in device["relays"]:
                if relay["function"] == relay_func:
                    status = relay["status"]
                    break

        no_ack = self.relay_subscriptions.get(relay_func, False)

        data = f"01{relay_func:03d}02{status}"
        msg = build_message(217, rev=1, data=data, no_ack=no_ack)
        self.send_to_client(msg)
        print(f"[Relay] Sent relay {relay_func} status: {status} (MID 0217)")

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
                    mid = log_msg[4:8]
                    data = log_msg[20:]
                    print(f"[Send] MID {mid} ({len(msg_bytes)} bytes): {data[:60]}...")
                    if hasattr(self, '_gui_log_message'):
                        self._gui_log_message("send", mid, len(msg_bytes), data)
                except (OSError, BrokenPipeError, ConnectionResetError) as e:
                    print(f"[Send Error] Connection issue: {e}")
                    try: self.client_socket.close()
                    except OSError: pass
                    self.client_socket = None
                    self.session_active = False
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
                mid = log_msg_recv[4:8]
                data = log_msg_recv[20:]
                print(f"[Recv] MID {mid} ({len(full_msg)} bytes): {data[:60]}...")
                if hasattr(self, '_gui_log_message'):
                    self._gui_log_message("recv", mid, len(full_msg), data)
                buffer = buffer[length+1:]
                self.process_message(full_msg)

        print(f"[Client] Cleaning up connection from {addr}.")
        self.session_active = False
        self.vin_subscribed = False; self.result_subscribed = False; self.pset_subscribed = False
        self.multi_spindle_subscribed = False
        self.multi_spindle_no_ack = False
        self.pset_subscribed_rev = 1
        self.vin_subscribed_rev = 1
        self.result_subscribed_rev = 1
        self.relay_subscriptions = {}
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

        if hasattr(self, '_gui_update_last_result'):
            self._gui_update_last_result(status, actual_torque, actual_angle, self.tightening_id_counter)

        if batch_completed:
            print("[Batch] Batch complete!")
            self._increment_vin()
            with self.state_lock:
                self.batch_counter = 0
            print("[Batch] VIN incremented and counter reset.")

    def send_multi_spindle_result(self):
        """Generate and send a simulated MID 0101 multi-spindle result (supports Rev 1-5)."""
        if not self.tool_enabled:
            print("[MultiSpindle] Send prevented: Tool is disabled.")
            return
        if not self.session_active or not self.multi_spindle_subscribed:
            print("[MultiSpindle] Send prevented: Session inactive or not subscribed.")
            return

        self.sync_tightening_id = (self.sync_tightening_id + 1) % 65536
        timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d:%H:%M:%S")
        revision = self.multi_spindle_requested_rev

        current_pset_params = self.pset_parameters.get(self.current_pset)
        if current_pset_params:
            target_torque = current_pset_params["target_torque"]
            torque_min = current_pset_params["torque_min"]
            torque_max = current_pset_params["torque_max"]
            target_angle = current_pset_params["target_angle"]
            angle_min = current_pset_params["angle_min"]
            angle_max = current_pset_params["angle_max"]
            batch_size = current_pset_params["batch_size"]
        else:
            target_torque, torque_min, torque_max = 50.00, 47.00, 53.00
            target_angle, angle_min, angle_max = 90, 80, 100
            batch_size = self.target_batch_size

        pset_change_ts = (self.pset_last_change.strftime("%Y-%m-%d:%H:%M:%S")
                          if self.pset_last_change else timestamp_str)

        fields = []
        fields.append(f"01{self.num_spindles:02d}")
        fields.append(f"02{self.current_vin.ljust(25)[:25]}")
        fields.append(f"03{0:02d}")
        fields.append(f"04{(self.current_pset if self.current_pset else '0').rjust(3, '0')}")
        fields.append(f"05{batch_size:04d}")
        fields.append(f"06{self.batch_counter:04d}")
        fields.append(f"07{'0'}")
        fields.append(f"08{int(torque_min * 100):06d}")
        fields.append(f"09{int(torque_max * 100):06d}")
        fields.append(f"10{int(target_torque * 100):06d}")
        fields.append(f"11{int(angle_min):05d}")
        fields.append(f"12{int(angle_max):05d}")
        fields.append(f"13{int(target_angle):05d}")
        fields.append(f"14{pset_change_ts}")
        fields.append(f"15{timestamp_str}")
        fields.append(f"16{self.sync_tightening_id:05d}")

        spindle_results = []
        all_ok = True
        for spindle_num in range(1, self.num_spindles + 1):
            is_nok = random.random() < self.nok_probability
            status = "0" if is_nok else "1"
            if is_nok:
                all_ok = False

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

            spindle_results.append({
                "num": spindle_num,
                "channel": spindle_num,
                "status": status,
                "torque_status": torque_status,
                "angle_status": angle_status,
                "torque": int(actual_torque * 100),
                "angle": int(actual_angle)
            })

        overall_status = "1" if all_ok else "0"
        fields.append(f"17{overall_status}")

        spindle_data = ""
        for s in spindle_results:
            spindle_data += f"{s['num']:02d}{s['channel']:02d}{s['status']}{s['torque_status']}{s['torque']:06d}{s['angle_status']}{s['angle']:05d}"
        fields.append(f"18{spindle_data}")

        if revision >= 4:
            fields.append(f"19{'001'}")

        if revision >= 5:
            fields.append(f"20{0:05d}")

        data = "".join(fields)
        result_msg = build_message(101, rev=revision, data=data, no_ack=self.multi_spindle_no_ack)
        self.send_to_client(result_msg)
        print(f"[MultiSpindle] Sent result (MID 0101 rev {revision}, SyncID: {self.sync_tightening_id:05d}). Status: {'OK' if all_ok else 'NOK'}, Spindles: {self.num_spindles}")

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
        """Start Tkinter GUI with tabbed configuration and persistent status/log panels."""
        window_title = f"{self.controller_name.strip()} (Port: {self.port})"
        root = tk.Tk()
        root.title(window_title)
        root.geometry("1100x700")
        root.minsize(900, 600)
        root.configure(bg="#1a1a2e")

        style = ttk.Style()
        style.theme_use('clam')

        style.configure(".",
            background="#1a1a2e",
            foreground="#e8e8e8",
            fieldbackground="#16213e",
            font=("Consolas", 9))

        style.configure("TNotebook",
            background="#1a1a2e",
            borderwidth=0,
            padding=0)
        style.configure("TNotebook.Tab",
            background="#16213e",
            foreground="#8892b0",
            padding=[16, 8],
            font=("Consolas", 10, "bold"))
        style.map("TNotebook.Tab",
            background=[("selected", "#0f3460"), ("active", "#1a1a2e")],
            foreground=[("selected", "#00d9ff"), ("active", "#e8e8e8")],
            expand=[("selected", [0, 0, 0, 2])])

        style.configure("TFrame", background="#1a1a2e")
        style.configure("TLabel", background="#1a1a2e", foreground="#e8e8e8", font=("Consolas", 9))
        style.configure("TButton",
            background="#0f3460",
            foreground="#00d9ff",
            borderwidth=1,
            focuscolor="#00d9ff",
            font=("Consolas", 9, "bold"),
            padding=[12, 6])
        style.map("TButton",
            background=[("active", "#1a4a7a"), ("pressed", "#00d9ff")],
            foreground=[("pressed", "#1a1a2e")])

        style.configure("TEntry",
            fieldbackground="#16213e",
            foreground="#e8e8e8",
            insertcolor="#00d9ff",
            borderwidth=1,
            padding=[4, 4])

        style.configure("TSpinbox",
            fieldbackground="#16213e",
            foreground="#e8e8e8",
            arrowcolor="#00d9ff",
            borderwidth=1)

        style.configure("TCombobox",
            fieldbackground="#16213e",
            foreground="#e8e8e8",
            arrowcolor="#00d9ff",
            selectbackground="#0f3460",
            selectforeground="#00d9ff")
        style.map("TCombobox",
            fieldbackground=[("readonly", "#16213e")],
            selectbackground=[("readonly", "#0f3460")])

        style.configure("TCheckbutton",
            background="#1a1a2e",
            foreground="#e8e8e8",
            indicatorcolor="#16213e",
            indicatorrelief="flat",
            font=("Consolas", 9))
        style.map("TCheckbutton",
            indicatorcolor=[("selected", "#00d9ff"), ("active", "#0f3460")])

        style.configure("TLabelframe",
            background="#1a1a2e",
            foreground="#00d9ff",
            bordercolor="#0f3460",
            relief="solid",
            borderwidth=1)
        style.configure("TLabelframe.Label",
            background="#1a1a2e",
            foreground="#00d9ff",
            font=("Consolas", 10, "bold"))

        style.configure("Status.TLabel",
            background="#0f3460",
            foreground="#e8e8e8",
            font=("Consolas", 9),
            padding=[8, 4])
        style.configure("StatusValue.TLabel",
            background="#0f3460",
            foreground="#00d9ff",
            font=("Consolas", 10, "bold"),
            padding=[8, 4])
        style.configure("StatusOK.TLabel",
            background="#0f3460",
            foreground="#00ff88",
            font=("Consolas", 10, "bold"),
            padding=[8, 4])
        style.configure("StatusWarn.TLabel",
            background="#0f3460",
            foreground="#ffaa00",
            font=("Consolas", 10, "bold"),
            padding=[8, 4])
        style.configure("StatusError.TLabel",
            background="#0f3460",
            foreground="#ff4757",
            font=("Consolas", 10, "bold"),
            padding=[8, 4])

        style.configure("Control.TButton",
            background="#16213e",
            foreground="#e8e8e8",
            font=("Consolas", 9),
            padding=[10, 6])
        style.map("Control.TButton",
            background=[("active", "#1a4a7a"), ("pressed", "#00d9ff")],
            foreground=[("pressed", "#1a1a2e")])

        style.configure("Primary.TButton",
            background="#0f3460",
            foreground="#00d9ff",
            font=("Consolas", 10, "bold"),
            padding=[14, 8])
        style.map("Primary.TButton",
            background=[("active", "#1a4a7a"), ("pressed", "#00d9ff")],
            foreground=[("pressed", "#1a1a2e")])

        vin_var = tk.StringVar(value=self.current_vin)
        batch_size_var = tk.StringVar(value=str(self.target_batch_size))
        nok_prob_var = tk.StringVar(value=str(int(self.nok_probability * 100)))
        auto_loop_interval_var = tk.StringVar(value=str(self.auto_loop_interval))
        auto_send_loop_status_var = tk.StringVar(value="ACTIVE")
        pset_display_var = tk.StringVar(value="Not set")
        conn_display_var = tk.StringVar(value="DISCONNECTED")
        batch_display_var = tk.StringVar(value=f"{self.batch_counter}/{self.target_batch_size}")
        vin_display_var = tk.StringVar(value=self.current_vin)
        tool_protocol_status_var = tk.StringVar(value="ENABLED")

        rev_mid_0002_var = tk.StringVar(value=str(self.revision_config.get(2, 6)))
        rev_mid_0004_var = tk.StringVar(value=str(self.revision_config.get(4, 3)))
        rev_mid_0015_var = tk.StringVar(value=str(self.revision_config.get(15, 2)))
        rev_mid_0041_var = tk.StringVar(value=str(self.revision_config.get(41, 5)))
        rev_mid_0052_var = tk.StringVar(value=str(self.revision_config.get(52, 2)))
        rev_mid_0061_var = tk.StringVar(value=str(self.revision_config.get(61, 7)))
        rev_mid_0101_var = tk.StringVar(value=str(self.revision_config.get(101, 5)))
        rev_mid_0215_var = tk.StringVar(value=str(self.revision_config.get(215, 2)))

        profile_var = tk.StringVar(value=self.get_current_profile())

        pset_id_var = tk.StringVar(value=list(self.available_psets)[0] if self.available_psets else "")
        pset_batch_size_var = tk.StringVar(value="")
        pset_target_torque_var = tk.StringVar(value="")
        pset_torque_min_var = tk.StringVar(value="")
        pset_torque_max_var = tk.StringVar(value="")
        pset_target_angle_var = tk.StringVar(value="")
        pset_angle_min_var = tk.StringVar(value="")
        pset_angle_max_var = tk.StringVar(value="")

        log_to_file_var = tk.BooleanVar(value=False)
        log_file_handle = [None]
        hide_keepalive_var = tk.BooleanVar(value=False)

        last_result_status_var = tk.StringVar(value="---")
        last_result_torque_var = tk.StringVar(value="---")
        last_result_angle_var = tk.StringVar(value="---")
        last_result_id_var = tk.StringVar(value="---")

        def parse_mid_fields(mid: str, data: str) -> str:
            """Parse known MID data into human-readable field breakdown."""
            try:
                if mid == "0061":
                    fields = []
                    if len(data) >= 6 and data[0:2] == "01":
                        fields.append(f"Cell={data[2:6]}")
                    if len(data) >= 10 and data[6:8] == "02":
                        fields.append(f"Ch={data[8:10]}")
                    if len(data) >= 37 and data[10:12] == "03":
                        fields.append(f"Ctrl={data[12:37].strip()}")
                    if len(data) >= 64 and data[37:39] == "04":
                        fields.append(f"VIN={data[39:64].strip()}")
                    if len(data) >= 68 and data[64:66] == "05":
                        fields.append(f"Job={data[66:68]}")
                    if len(data) >= 73 and data[68:70] == "06":
                        fields.append(f"Pset={data[70:73]}")
                    if len(data) >= 79 and data[73:75] == "07":
                        fields.append(f"BatchSz={data[75:79]}")
                    if len(data) >= 85 and data[79:81] == "08":
                        fields.append(f"BatchCnt={data[81:85]}")
                    if len(data) >= 88 and data[85:87] == "09":
                        status = "OK" if data[87] == "1" else "NOK"
                        fields.append(f"Status={status}")
                    if len(data) >= 91 and data[88:90] == "10":
                        fields.append(f"TqSt={data[90]}")
                    if len(data) >= 94 and data[91:93] == "11":
                        fields.append(f"AngSt={data[93]}")
                    if len(data) >= 102 and data[94:96] == "12":
                        fields.append(f"TqMin={int(data[96:102])/100:.2f}")
                    if len(data) >= 110 and data[102:104] == "13":
                        fields.append(f"TqMax={int(data[104:110])/100:.2f}")
                    if len(data) >= 118 and data[110:112] == "14":
                        fields.append(f"TqTgt={int(data[112:118])/100:.2f}")
                    if len(data) >= 126 and data[118:120] == "15":
                        fields.append(f"TqFin={int(data[120:126])/100:.2f}")
                    if len(data) >= 133 and data[126:128] == "16":
                        fields.append(f"AngMin={data[128:133]}")
                    if len(data) >= 140 and data[133:135] == "17":
                        fields.append(f"AngMax={data[135:140]}")
                    if len(data) >= 147 and data[140:142] == "18":
                        fields.append(f"AngTgt={data[142:147]}")
                    if len(data) >= 154 and data[147:149] == "19":
                        fields.append(f"AngFin={data[149:154]}")
                    if len(data) >= 175 and data[154:156] == "20":
                        fields.append(f"Time={data[156:175]}")
                    if len(data) >= 199 and data[178:180] == "22":
                        fields.append(f"BatchSt={data[180]}")
                    if len(data) >= 213 and data[181:183] == "23":
                        fields.append(f"TightID={data[183:193]}")
                    return " | ".join(fields) if fields else None
                elif mid == "0052":
                    if len(data) >= 27 and data[0:2] == "01":
                        return f"VIN={data[2:27].strip()}"
                    else:
                        return f"VIN={data[:25].strip()}"
                elif mid == "0015":
                    if len(data) >= 5 and data[0:2] == "01":
                        return f"Pset={data[2:5]}"
                    else:
                        return f"Pset={data[:3]}"
                elif mid == "0002":
                    fields = []
                    if len(data) >= 6 and data[0:2] == "01":
                        fields.append(f"Cell={data[2:6]}")
                    if len(data) >= 10 and data[6:8] == "02":
                        fields.append(f"Ch={data[8:10]}")
                    if len(data) >= 37 and data[10:12] == "03":
                        fields.append(f"Name={data[12:37].strip()}")
                    return " | ".join(fields) if fields else None
                elif mid == "0001":
                    return "Communication Start Request"
                elif mid == "0003":
                    return "Communication Stop Request"
                elif mid == "0005":
                    if len(data) >= 4:
                        return f"Ack for MID {data[:4]}"
                    return "Command Accepted"
                elif mid == "0004":
                    if len(data) >= 6:
                        return f"Error: MID={data[:4]} Code={data[4:6]}"
                    return "Command Error"
                elif mid == "0018":
                    return f"Select Pset={data.strip()}"
                elif mid == "0060":
                    return "Subscribe to Results"
                elif mid == "0014":
                    return "Subscribe to Pset"
                elif mid == "0050":
                    return "Subscribe to VIN"
                elif mid == "9999":
                    return "Keep-Alive"
                elif mid == "0101":
                    fields = []
                    if len(data) >= 4 and data[0:2] == "01":
                        fields.append(f"Spindles={data[2:4]}")
                    if len(data) >= 31 and data[4:6] == "02":
                        fields.append(f"VIN={data[6:31].strip()}")
                    if len(data) >= 42 and data[34:36] == "04":
                        fields.append(f"Pset={data[36:39]}")
                    if len(data) >= 70 and data[53:55] == "17":
                        status = "OK" if data[55] == "1" else "NOK"
                        fields.append(f"Status={status}")
                    return " | ".join(fields) if fields else None
            except (ValueError, IndexError):
                pass
            return None

        def log_message(direction: str, mid: str, length: int, data: str):
            if hide_keepalive_var.get() and mid == "9999":
                return

            timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            prefix = ">>>" if direction == "send" else "<<<"
            color_tag = "send" if direction == "send" else "recv"
            log_line = f"{timestamp} {prefix} MID {mid} ({length}B): {data}\n"

            parsed = parse_mid_fields(mid, data)
            if parsed:
                log_line += f"         {parsed}\n"

            try:
                log_text.configure(state='normal')
                log_text.insert(tk.END, log_line, color_tag)
                log_text.see(tk.END)
                log_text.configure(state='disabled')

                if log_to_file_var.get() and log_file_handle[0]:
                    log_file_handle[0].write(log_line)
                    log_file_handle[0].flush()
            except tk.TclError:
                pass

        self._gui_log_message = log_message

        def update_last_result(status: str, torque: float, angle: float, tightening_id: int):
            status_text = "OK" if status == "1" else "NOK"
            last_result_status_var.set(status_text)
            last_result_torque_var.set(f"{torque:.2f} Nm")
            last_result_angle_var.set(f"{angle:.0f}°")
            last_result_id_var.set(str(tightening_id))

        self._gui_update_last_result = update_last_result

        def apply_global_settings():
            try:
                new_vin = vin_var.get()
                if new_vin != self.current_vin:
                    if self._parse_vin(new_vin):
                        self.current_vin = new_vin
                        with self.state_lock:
                            self.batch_counter = 0
                        log_message("info", "----", 0, f"VIN set to {self.current_vin}")
                    else:
                        messagebox.showerror("Error", f"Invalid VIN format: {new_vin}")
                        vin_var.set(self.current_vin)
                        return

                new_batch_size = int(batch_size_var.get())
                if new_batch_size >= 0:
                    self.target_batch_size = new_batch_size
                else:
                    messagebox.showerror("Error", "Batch Size must be >= 0")
                    batch_size_var.set(str(self.target_batch_size))
                    return

                new_nok_prob_pct = int(nok_prob_var.get())
                if 0 <= new_nok_prob_pct <= 100:
                    self.nok_probability = new_nok_prob_pct / 100.0
                else:
                    messagebox.showerror("Error", "NOK % must be 0-100")
                    nok_prob_var.set(str(int(self.nok_probability * 100)))
                    return

                new_interval = int(auto_loop_interval_var.get())
                if new_interval > 0:
                    self.auto_loop_interval = new_interval
                else:
                    messagebox.showerror("Error", "Interval must be > 0")
                    auto_loop_interval_var.set(str(self.auto_loop_interval))
                    return

                update_labels()
            except ValueError:
                messagebox.showerror("Error", "Invalid number format for Batch Size, NOK %, or Interval.")
                batch_size_var.set(str(self.target_batch_size))
                nok_prob_var.set(str(int(self.nok_probability * 100)))
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
            new_status = "ACTIVE" if self.auto_send_loop_active else "PAUSED"
            auto_send_loop_status_var.set(new_status)

        def manual_send_result():
            threading.Thread(target=self.send_single_tightening_result, daemon=True).start()

        def update_labels():
            pset_display_var.set(self.current_pset if self.current_pset else "---")
            conn_display_var.set("CONNECTED" if self.session_active else "DISCONNECTED")
            current_target_batch = self.pset_parameters.get(self.current_pset, {}).get("batch_size", self.target_batch_size)
            with self.state_lock:
                current_batch = self.batch_counter
            batch_display_var.set(f"{current_batch}/{current_target_batch}")
            vin_display_var.set(self.current_vin)
            tool_protocol_status_var.set("ENABLED" if self.tool_enabled else "DISABLED")

            conn_label.configure(style="StatusOK.TLabel" if self.session_active else "StatusError.TLabel")
            tool_label.configure(style="StatusOK.TLabel" if self.tool_enabled else "StatusWarn.TLabel")

            result_status = last_result_status_var.get()
            if result_status == "OK":
                result_status_label.configure(style="StatusOK.TLabel")
            elif result_status == "NOK":
                result_status_label.configure(style="StatusError.TLabel")
            else:
                result_status_label.configure(style="StatusValue.TLabel")

            try:
                root.after(500, update_labels)
            except tk.TclError:
                pass

        def clear_log():
            log_text.configure(state='normal')
            log_text.delete(1.0, tk.END)
            log_text.configure(state='disabled')

        def save_log():
            filepath = filedialog.asksaveasfilename(
                defaultextension=".log",
                filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
                title="Save Communication Log"
            )
            if filepath:
                try:
                    with open(filepath, 'w') as f:
                        f.write(log_text.get(1.0, tk.END))
                    messagebox.showinfo("Success", f"Log saved to {filepath}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save log: {e}")

        def toggle_file_logging():
            if log_to_file_var.get():
                filepath = filedialog.asksaveasfilename(
                    defaultextension=".log",
                    filetypes=[("Log files", "*.log"), ("Text files", "*.txt")],
                    title="Select Live Log File"
                )
                if filepath:
                    try:
                        log_file_handle[0] = open(filepath, 'a')
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to open log file: {e}")
                        log_to_file_var.set(False)
                else:
                    log_to_file_var.set(False)
            else:
                if log_file_handle[0]:
                    log_file_handle[0].close()
                    log_file_handle[0] = None

        def apply_revision_settings():
            try:
                self.set_max_revision(2, int(rev_mid_0002_var.get()))
                self.set_max_revision(4, int(rev_mid_0004_var.get()))
                self.set_max_revision(15, int(rev_mid_0015_var.get()))
                self.set_max_revision(41, int(rev_mid_0041_var.get()))
                self.set_max_revision(52, int(rev_mid_0052_var.get()))
                self.set_max_revision(61, int(rev_mid_0061_var.get()))
                self.set_max_revision(101, int(rev_mid_0101_var.get()))
                self.set_max_revision(215, int(rev_mid_0215_var.get()))
                self.current_profile = "custom"
                print("[GUI] Applied revision configuration:")
                for mid, rev in sorted(self.revision_config.items()):
                    print(f"  MID {mid:04d}: rev {rev}")
            except ValueError as e:
                messagebox.showerror("Error", f"Invalid revision value: {e}")

        def apply_profile_selection():
            selected_profile = profile_var.get()
            try:
                self.apply_profile(selected_profile)
                rev_mid_0002_var.set(str(self.revision_config.get(2, 6)))
                rev_mid_0004_var.set(str(self.revision_config.get(4, 3)))
                rev_mid_0015_var.set(str(self.revision_config.get(15, 2)))
                rev_mid_0041_var.set(str(self.revision_config.get(41, 5)))
                rev_mid_0052_var.set(str(self.revision_config.get(52, 2)))
                rev_mid_0061_var.set(str(self.revision_config.get(61, 7)))
                rev_mid_0101_var.set(str(self.revision_config.get(101, 5)))
                rev_mid_0215_var.set(str(self.revision_config.get(215, 2)))
                print(f"[GUI] Applied profile: {selected_profile}")
                print(f"  Description: {self.get_profile_description(selected_profile)}")
            except ValueError as e:
                messagebox.showerror("Error", str(e))

        def refresh_profile_dropdown():
            """Refresh the profile dropdown with current available profiles."""
            profile_menu['values'] = self.get_available_profiles()

        def save_profile_dialog():
            """Open dialog to save current settings as a new profile."""
            self.set_max_revision(2, int(rev_mid_0002_var.get()))
            self.set_max_revision(4, int(rev_mid_0004_var.get()))
            self.set_max_revision(15, int(rev_mid_0015_var.get()))
            self.set_max_revision(41, int(rev_mid_0041_var.get()))
            self.set_max_revision(52, int(rev_mid_0052_var.get()))
            self.set_max_revision(61, int(rev_mid_0061_var.get()))
            self.set_max_revision(101, int(rev_mid_0101_var.get()))
            self.set_max_revision(215, int(rev_mid_0215_var.get()))

            dialog = tk.Toplevel(root)
            dialog.title("Save Profile")
            dialog.geometry("350x150")
            dialog.transient(root)
            dialog.grab_set()

            tk.Label(dialog, text="Profile Name:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=10)
            name_entry = tk.Entry(dialog, width=30)
            name_entry.grid(row=0, column=1, padx=10, pady=10)
            name_entry.insert(0, "my-controller")

            tk.Label(dialog, text="Description:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
            desc_entry = tk.Entry(dialog, width=30)
            desc_entry.grid(row=1, column=1, padx=10, pady=5)
            desc_entry.insert(0, "Custom controller profile")

            def do_save():
                profile_name = name_entry.get().strip()
                description = desc_entry.get().strip()
                if not profile_name:
                    messagebox.showerror("Error", "Profile name is required")
                    return
                if profile_name in self.DEFAULT_PROFILES:
                    messagebox.showerror("Error", f"Cannot overwrite built-in profile: {profile_name}")
                    return
                profile_name = profile_name.replace(" ", "-").lower()
                try:
                    if not os.path.exists(CONTROLLERS_DIR):
                        os.makedirs(CONTROLLERS_DIR)
                    filepath = os.path.join(CONTROLLERS_DIR, f"{profile_name}.json")
                    profile_data = {
                        "name": profile_name,
                        "description": description,
                        "revisions": dict(self.revision_config)
                    }
                    with open(filepath, 'w') as f:
                        json.dump(profile_data, f, indent=2)
                    self.current_profile = profile_name
                    profile_var.set(profile_name)
                    refresh_profile_dropdown()
                    print(f"[GUI] Saved profile '{profile_name}' to: {filepath}")
                    messagebox.showinfo("Success", f"Profile '{profile_name}' saved")
                    dialog.destroy()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save profile: {e}")

            btn_frame = tk.Frame(dialog)
            btn_frame.grid(row=2, column=0, columnspan=2, pady=15)
            tk.Button(btn_frame, text="Save", command=do_save, width=10).pack(side=tk.LEFT, padx=5)
            tk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=10).pack(side=tk.LEFT, padx=5)

            name_entry.focus_set()

        def load_profile_from_file():
            filepath = filedialog.askopenfilename(
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                title="Load Profile"
            )
            if filepath:
                try:
                    loaded_name = self.load_profile_from_file(filepath)
                    profile_var.set(loaded_name)
                    rev_mid_0002_var.set(str(self.revision_config.get(2, 6)))
                    rev_mid_0004_var.set(str(self.revision_config.get(4, 3)))
                    rev_mid_0015_var.set(str(self.revision_config.get(15, 2)))
                    rev_mid_0041_var.set(str(self.revision_config.get(41, 5)))
                    rev_mid_0052_var.set(str(self.revision_config.get(52, 2)))
                    rev_mid_0061_var.set(str(self.revision_config.get(61, 7)))
                    rev_mid_0101_var.set(str(self.revision_config.get(101, 5)))
                    rev_mid_0215_var.set(str(self.revision_config.get(215, 2)))
                    messagebox.showinfo("Success", f"Profile '{loaded_name}' loaded")
                except FileNotFoundError:
                    messagebox.showerror("Error", f"File not found: {filepath}")
                except ValueError as e:
                    messagebox.showerror("Error", f"Invalid profile file: {e}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load profile: {e}")

        main_container = ttk.Frame(root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        top_section = ttk.Frame(main_container)
        top_section.pack(fill=tk.BOTH, expand=True)

        notebook = ttk.Notebook(top_section)
        notebook.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        global_tab = ttk.Frame(notebook, padding=12)
        notebook.add(global_tab, text="  GLOBAL  ")

        ttk.Label(global_tab, text="SIMULATION PARAMETERS", font=("Consolas", 11, "bold")).grid(
            row=0, column=0, columnspan=4, sticky=tk.W, pady=(0, 12))

        ttk.Label(global_tab, text="Initial VIN:").grid(row=1, column=0, sticky=tk.W, pady=6)
        ttk.Entry(global_tab, textvariable=vin_var, width=24).grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=(8, 0))

        ttk.Label(global_tab, text="Global Batch Size:").grid(row=2, column=0, sticky=tk.W, pady=6)
        ttk.Entry(global_tab, textvariable=batch_size_var, width=8).grid(row=2, column=1, sticky=tk.W, padx=(8, 0))

        ttk.Label(global_tab, text="NOK Probability %:").grid(row=3, column=0, sticky=tk.W, pady=6)
        ttk.Entry(global_tab, textvariable=nok_prob_var, width=8).grid(row=3, column=1, sticky=tk.W, padx=(8, 0))

        ttk.Label(global_tab, text="Auto Loop Interval (s):").grid(row=4, column=0, sticky=tk.W, pady=6)
        ttk.Entry(global_tab, textvariable=auto_loop_interval_var, width=8).grid(row=4, column=1, sticky=tk.W, padx=(8, 0))

        ttk.Button(global_tab, text="Apply Settings", command=apply_global_settings, style="Primary.TButton").grid(
            row=5, column=0, columnspan=2, pady=(16, 8), sticky=tk.W)

        ttk.Separator(global_tab, orient=tk.HORIZONTAL).grid(row=6, column=0, columnspan=4, sticky=tk.EW, pady=16)

        ttk.Label(global_tab, text="CONTROLS", font=("Consolas", 11, "bold")).grid(
            row=7, column=0, columnspan=4, sticky=tk.W, pady=(0, 12))

        control_frame = ttk.Frame(global_tab)
        control_frame.grid(row=8, column=0, columnspan=4, sticky=tk.W)

        ttk.Button(control_frame, text="Toggle Auto Loop", command=toggle_auto_send_loop, style="Control.TButton").pack(
            side=tk.LEFT, padx=(0, 8))
        auto_status_label = ttk.Label(control_frame, textvariable=auto_send_loop_status_var, style="StatusValue.TLabel", width=10, anchor="center")
        auto_status_label.pack(side=tk.LEFT, padx=(0, 16))
        ttk.Button(control_frame, text="Send Single Result", command=manual_send_result, style="Control.TButton").pack(
            side=tk.LEFT)

        pset_tab = ttk.Frame(notebook, padding=12)
        notebook.add(pset_tab, text="  PSET CONFIG  ")

        ttk.Label(pset_tab, text="PARAMETER SET CONFIGURATION", font=("Consolas", 11, "bold")).grid(
            row=0, column=0, columnspan=6, sticky=tk.W, pady=(0, 12))

        ttk.Label(pset_tab, text="Pset ID:").grid(row=1, column=0, sticky=tk.W, pady=6)
        pset_combo = ttk.Combobox(pset_tab, textvariable=pset_id_var, values=sorted(list(self.available_psets)), width=10, state="readonly")
        pset_combo.grid(row=1, column=1, sticky=tk.W, padx=(8, 0))
        ttk.Button(pset_tab, text="Load", command=load_pset_settings, style="Control.TButton").grid(
            row=1, column=2, padx=(16, 0))

        ttk.Separator(pset_tab, orient=tk.HORIZONTAL).grid(row=2, column=0, columnspan=6, sticky=tk.EW, pady=16)

        ttk.Label(pset_tab, text="Batch Size:").grid(row=3, column=0, sticky=tk.W, pady=6)
        ttk.Entry(pset_tab, textvariable=pset_batch_size_var, width=8).grid(row=3, column=1, sticky=tk.W, padx=(8, 0))

        ttk.Label(pset_tab, text="TORQUE LIMITS", font=("Consolas", 10, "bold")).grid(
            row=4, column=0, columnspan=6, sticky=tk.W, pady=(16, 8))

        torque_frame = ttk.Frame(pset_tab)
        torque_frame.grid(row=5, column=0, columnspan=6, sticky=tk.W)
        ttk.Label(torque_frame, text="Target:").pack(side=tk.LEFT)
        ttk.Entry(torque_frame, textvariable=pset_target_torque_var, width=8).pack(side=tk.LEFT, padx=(4, 16))
        ttk.Label(torque_frame, text="Min:").pack(side=tk.LEFT)
        ttk.Entry(torque_frame, textvariable=pset_torque_min_var, width=8).pack(side=tk.LEFT, padx=(4, 16))
        ttk.Label(torque_frame, text="Max:").pack(side=tk.LEFT)
        ttk.Entry(torque_frame, textvariable=pset_torque_max_var, width=8).pack(side=tk.LEFT, padx=(4, 0))

        ttk.Label(pset_tab, text="ANGLE LIMITS", font=("Consolas", 10, "bold")).grid(
            row=6, column=0, columnspan=6, sticky=tk.W, pady=(16, 8))

        angle_frame = ttk.Frame(pset_tab)
        angle_frame.grid(row=7, column=0, columnspan=6, sticky=tk.W)
        ttk.Label(angle_frame, text="Target:").pack(side=tk.LEFT)
        ttk.Entry(angle_frame, textvariable=pset_target_angle_var, width=8).pack(side=tk.LEFT, padx=(4, 16))
        ttk.Label(angle_frame, text="Min:").pack(side=tk.LEFT)
        ttk.Entry(angle_frame, textvariable=pset_angle_min_var, width=8).pack(side=tk.LEFT, padx=(4, 16))
        ttk.Label(angle_frame, text="Max:").pack(side=tk.LEFT)
        ttk.Entry(angle_frame, textvariable=pset_angle_max_var, width=8).pack(side=tk.LEFT, padx=(4, 0))

        ttk.Button(pset_tab, text="Apply Pset Settings", command=apply_pset_settings, style="Primary.TButton").grid(
            row=8, column=0, columnspan=3, pady=(20, 8), sticky=tk.W)

        revision_tab = ttk.Frame(notebook, padding=12)
        notebook.add(revision_tab, text="  REVISIONS  ")

        ttk.Label(revision_tab, text="MID REVISION CONFIGURATION", font=("Consolas", 11, "bold")).grid(
            row=0, column=0, columnspan=6, sticky=tk.W, pady=(0, 12))

        profile_frame = ttk.Frame(revision_tab)
        profile_frame.grid(row=1, column=0, columnspan=6, sticky=tk.W, pady=(0, 16))
        ttk.Label(profile_frame, text="Profile:").pack(side=tk.LEFT)
        profile_combo = ttk.Combobox(profile_frame, textvariable=profile_var, values=self.get_available_profiles(), width=16, state="readonly")
        profile_combo.pack(side=tk.LEFT, padx=(8, 12))
        profile_menu = profile_combo
        ttk.Button(profile_frame, text="Apply", command=apply_profile_selection, style="Control.TButton").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(profile_frame, text="Save...", command=save_profile_dialog, style="Control.TButton").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(profile_frame, text="Load...", command=load_profile_from_file, style="Control.TButton").pack(side=tk.LEFT)

        ttk.Separator(revision_tab, orient=tk.HORIZONTAL).grid(row=2, column=0, columnspan=6, sticky=tk.EW, pady=8)

        mid_configs = [
            ("MID 0002", "Comm Start", rev_mid_0002_var, 1, 6),
            ("MID 0004", "Error", rev_mid_0004_var, 1, 3),
            ("MID 0015", "Pset", rev_mid_0015_var, 1, 2),
            ("MID 0041", "Tool Data", rev_mid_0041_var, 1, 5),
            ("MID 0052", "VIN", rev_mid_0052_var, 1, 2),
            ("MID 0061", "Result", rev_mid_0061_var, 1, 7),
            ("MID 0101", "Multi-Spindle", rev_mid_0101_var, 1, 5),
            ("MID 0215", "I/O Status", rev_mid_0215_var, 1, 2),
        ]

        for idx, (mid, desc, var, min_val, max_val) in enumerate(mid_configs):
            row = 3 + (idx // 2)
            col = (idx % 2) * 3
            ttk.Label(revision_tab, text=f"{mid} ({desc}):").grid(row=row, column=col, sticky=tk.W, pady=4, padx=(0, 4))
            ttk.Spinbox(revision_tab, from_=min_val, to=max_val, textvariable=var, width=4).grid(
                row=row, column=col+1, sticky=tk.W, padx=(0, 24))

        ttk.Button(revision_tab, text="Apply Revisions", command=apply_revision_settings, style="Primary.TButton").grid(
            row=8, column=0, columnspan=3, pady=(16, 8), sticky=tk.W)

        status_frame = ttk.LabelFrame(top_section, text="STATUS", padding=12)
        status_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 0))

        status_items = [
            ("Connection:", conn_display_var, "conn"),
            ("Tool:", tool_protocol_status_var, "tool"),
            ("Pset:", pset_display_var, "pset"),
            ("VIN:", vin_display_var, "vin"),
            ("Batch:", batch_display_var, "batch"),
            ("Auto Loop:", auto_send_loop_status_var, "loop"),
        ]

        conn_label = None
        tool_label = None
        result_status_label = None

        for idx, (label_text, var, key) in enumerate(status_items):
            ttk.Label(status_frame, text=label_text, style="Status.TLabel").grid(row=idx, column=0, sticky=tk.W, pady=4)
            lbl = ttk.Label(status_frame, textvariable=var, style="StatusValue.TLabel", width=14, anchor="e")
            lbl.grid(row=idx, column=1, sticky=tk.E, pady=4, padx=(8, 0))
            if key == "conn":
                conn_label = lbl
            elif key == "tool":
                tool_label = lbl

        ttk.Separator(status_frame, orient=tk.HORIZONTAL).grid(row=6, column=0, columnspan=2, sticky=tk.EW, pady=12)

        ttk.Label(status_frame, text="LAST RESULT", font=("Consolas", 9, "bold"), foreground="#00d9ff").grid(
            row=7, column=0, columnspan=2, sticky=tk.W, pady=(0, 8))

        result_items = [
            ("Status:", last_result_status_var, "result_status"),
            ("Torque:", last_result_torque_var, "torque"),
            ("Angle:", last_result_angle_var, "angle"),
            ("ID:", last_result_id_var, "id"),
        ]

        for idx, (label_text, var, key) in enumerate(result_items):
            ttk.Label(status_frame, text=label_text, style="Status.TLabel").grid(row=8+idx, column=0, sticky=tk.W, pady=2)
            lbl = ttk.Label(status_frame, textvariable=var, style="StatusValue.TLabel", width=14, anchor="e")
            lbl.grid(row=8+idx, column=1, sticky=tk.E, pady=2, padx=(8, 0))
            if key == "result_status":
                result_status_label = lbl

        log_frame = ttk.LabelFrame(main_container, text="COMMUNICATION LOG", padding=8)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        log_controls = ttk.Frame(log_frame)
        log_controls.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(log_controls, text="Clear", command=clear_log, style="Control.TButton").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(log_controls, text="Save Log...", command=save_log, style="Control.TButton").pack(side=tk.LEFT, padx=(0, 16))
        ttk.Checkbutton(log_controls, text="Live Log to File", variable=log_to_file_var, command=toggle_file_logging).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Checkbutton(log_controls, text="Hide Keep-Alive (9999)", variable=hide_keepalive_var).pack(side=tk.LEFT)

        log_container = ttk.Frame(log_frame)
        log_container.pack(fill=tk.BOTH, expand=True)

        log_text = tk.Text(
            log_container,
            height=10,
            wrap=tk.NONE,
            font=("Consolas", 9),
            bg="#0d1117",
            fg="#8b949e",
            insertbackground="#00d9ff",
            selectbackground="#1a4a7a",
            selectforeground="#e8e8e8",
            relief="flat",
            borderwidth=0,
            padx=8,
            pady=8
        )
        log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        log_scrollbar_y = ttk.Scrollbar(log_container, orient=tk.VERTICAL, command=log_text.yview)
        log_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        log_text.configure(yscrollcommand=log_scrollbar_y.set)

        log_scrollbar_x = ttk.Scrollbar(log_frame, orient=tk.HORIZONTAL, command=log_text.xview)
        log_scrollbar_x.pack(fill=tk.X)
        log_text.configure(xscrollcommand=log_scrollbar_x.set)

        log_text.tag_configure("send", foreground="#00d9ff")
        log_text.tag_configure("recv", foreground="#00ff88")
        log_text.tag_configure("info", foreground="#ffaa00")
        log_text.configure(state='disabled')

        def on_closing():
            if log_file_handle[0]:
                log_file_handle[0].close()
            self._save_pset_parameters(self.controller_name)
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_closing)
        pset_id_var.trace_add("write", lambda name, index, mode: load_pset_settings())
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
