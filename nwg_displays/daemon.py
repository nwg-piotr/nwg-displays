#!/usr/bin/env python3
import time
import os
import json
from nwg_displays.tools import list_outputs_activity, get_config_home, eprint, load_json
import argparse
import sys
    

class MonitorDaemon:
    def __init__(self, check_interval=5, config_backup_path=None):
        self.check_interval = check_interval
        self.previous_state = {}
        self.config_backup_path = config_backup_path or self._get_default_backup_path()
        self.laptop_only_config = None
        self.monitor_preferences = self._load_monitor_preferences()
        self.original_config = self._backup_current_config()
        self._detect_laptop_config()
        
    def _get_default_backup_path(self):
        if os.getenv("HYPRLAND_INSTANCE_SIGNATURE"):
            return os.path.join(get_config_home(), "hypr", "monitors.conf.backup")
        elif os.getenv("SWAYSOCK"):
            return os.path.join(get_config_home(), "sway", "outputs.backup")
        return None
    
    def monitor_loop(self):
        while True:
            current_state = list_outputs_activity()
            if self._state_changed(current_state):
                self._handle_state_change(current_state)
            self.previous_state = current_state
            time.sleep(self.check_interval)
    
    def _state_changed(self, current_state):
        return current_state != self.previous_state
    
    def _handle_state_change(self, current_state):
        # Handle monitor disconnections and reconnections differently
        if self._monitors_disconnected(current_state):
            self._handle_disconnect(current_state)
        elif self._monitors_connected(current_state):
            self._handle_reconnect(current_state)
    
    def _handle_disconnect(self, current_state):
        """Handle monitor disconnect - use preferences"""
        eprint("Monitor disconnected, waiting 1s before updating...")
        time.sleep(1)
        self._reset_config(current_state)
    
    def _handle_reconnect(self, current_state):
        """Handle monitor reconnect - only restore if it's a hardware reconnect"""
        eprint("Monitor reconnected, waiting 1s before checking config...")
        time.sleep(1)
        
        # Check if config was recently modified by user (nwg-displays or manual edit)
        config_path = os.path.join(get_config_home(), "hypr", "monitors.conf")
        if os.path.exists(config_path):
            config_mtime = os.path.getmtime(config_path)
            current_time = time.time()
            
            # If config was modified in last 10 seconds, assume user change - don't restore
            if current_time - config_mtime < 10:
                eprint("Config recently modified by user, not restoring original")
                # Update our backup to the new user config
                self.original_config = self._backup_current_config()
                return
        
        # Check if all monitors from original config are now active
        if self.original_config:
            original_monitors = set()
            for line in self.original_config.split('\n'):
                if line.startswith('monitor=') and not line.startswith('#'):
                    monitor_name = line.split(',')[0].split('=')[1]
                    original_monitors.add(monitor_name)
            
            # If all original monitors are now active, restore original config
            active_monitors = {name for name, active in current_state.items() if active}
            if original_monitors.issubset(active_monitors):
                if self._restore_original_config():
                    return
        
        # Otherwise, use preferences
        self._reset_config(current_state)
    
    def _monitors_connected(self, current_state):
        # Check if any monitor that was prev inactive is now active
        for monitor, is_active in current_state.items():
            if is_active and not self.previous_state.get(monitor, False):
                eprint(f"Detected {monitor} connected (was inactive, now active)")
                return True
        return False
    
    def _monitors_disconnected(self, current_state):
        # Check if any monitor that was prev active is now inactive
        for monitor, was_active in self.previous_state.items():
            if was_active and not current_state.get(monitor, False):
                eprint(f"Detected {monitor} disconnected (was active, now inactive)")
                return True
        return False
    
    def _detect_laptop_config(self):
        """Detect current laptop-only configuration from hyprctl"""
        if os.getenv("HYPRLAND_INSTANCE_SIGNATURE"):
            try:
                from nwg_displays.tools import hyprctl
                import json
                monitors = json.loads(hyprctl("j/monitors"))
                for monitor in monitors:
                    if "eDP" in monitor["name"]:
                        scale = round(monitor['scale'], 2)
                        refresh = round(monitor['refreshRate'], 2)
                        self.laptop_only_config = f"monitor={monitor['name']},{monitor['width']}x{monitor['height']}@{refresh},0x0,{scale}"
                        eprint(f"Detected laptop config: {self.laptop_only_config}")
                        break
            except Exception as e:
                eprint(f"Failed to detect laptop config: {e}")
                self.laptop_only_config = "monitor=eDP-1,preferred,0x0,1.0"
    
    def _load_monitor_preferences(self):
        """Load saved monitor preferences from JSON file"""
        prefs_file = os.path.join(get_config_home(), "nwg-displays", "monitor_preferences.json")
        if os.path.exists(prefs_file):
            prefs = load_json(prefs_file)
            if prefs:
                eprint(f"Loaded monitor preferences for: {list(prefs.keys())}")
                return prefs
        eprint("No monitor preferences found, using defaults")
        return {}
    
    def _backup_current_config(self):
        """Backup current monitors.conf as the 'usual' config"""
        if os.getenv("HYPRLAND_INSTANCE_SIGNATURE"):
            config_path = os.path.join(get_config_home(), "hypr", "monitors.conf")
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    original = f.read()
                eprint("Backed up current monitors.conf as usual config")
                return original
        return None
    
    def _restore_original_config(self):
        """Restore the original 'usual' config"""
        if self.original_config and os.getenv("HYPRLAND_INSTANCE_SIGNATURE"):
            config_path = os.path.join(get_config_home(), "hypr", "monitors.conf")
            with open(config_path, 'w') as f:
                f.write(self.original_config)
            eprint("Restored original usual config")
            return True
        return False
    
    def _backup_usual_config(self):
        usual_conf = os.path.join(get_config_home(),"nwg-displays","usual_conf.conf")
    
    def _reset_config(self, current_state):
        eprint("Monitor disconnected, updating config...")
        if os.getenv("HYPRLAND_INSTANCE_SIGNATURE"):
            config_path = os.path.join(get_config_home(), "hypr", "monitors.conf")
            #! pls add Sway support :D
            
            # Read existing config
            existing_lines = []
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    existing_lines = f.readlines()
            
            # Check if any monitors will be active after processing
            active_monitors = [name for name, active in current_state.items() if active]
            laptop_monitor = None
            for name in current_state.keys():
                if "eDP" in name or "LVDS" in name or "DSI" in name:
                    laptop_monitor = name
                    break
            
            # Force enable laptop if no other monitors active
            if not active_monitors and laptop_monitor:
                current_state[laptop_monitor] = True
                eprint(f"Force enabling {laptop_monitor} - no other monitors active")
            
            # Generate clean config
            with open(config_path, 'w') as f:
                f.write("# Updated by nwg-displays daemon\n")
                
                # Write config for all known monitors
                for monitor_name, is_active in current_state.items():
                    if is_active:
                        # Active monitor - use saved preferences or defaults
                        if monitor_name in self.monitor_preferences:
                            prefs = self.monitor_preferences[monitor_name]
                            config_line = f"monitor={monitor_name},{prefs['width']}x{prefs['height']}@{prefs['refresh']},{prefs['x']}x{prefs['y']},{prefs['scale']}"
                            f.write(f"{config_line}\n")
                            eprint(f"Enabled {monitor_name} with saved preferences")
                        else:
                            f.write(f"monitor={monitor_name},preferred,auto,1.0\n")
                            eprint(f"Enabled {monitor_name} with default settings")
                    else:
                        # Inactive monitor - disable it
                        f.write(f"monitor={monitor_name},disable\n")
                        eprint(f"Disabled {monitor_name}")
            
            eprint(f"Updated {config_path}")


def main():
    parser = argparse.ArgumentParser(description='nwg-displays monitor daemon')
    parser.add_argument('--interval', type=int, default=5, 
                       help='Check interval in seconds (default: 5)')
    args = parser.parse_args()
    
    if not (os.getenv("SWAYSOCK") or os.getenv("HYPRLAND_INSTANCE_SIGNATURE")):
        eprint("Neither sway nor Hyprland detected, terminating")
        sys.exit(1)
    
    eprint(f"Starting nwg-displays daemon with {args.interval}s interval")
    daemon = MonitorDaemon(check_interval=args.interval)
    
    try:
        daemon.monitor_loop()
    except KeyboardInterrupt:
        eprint("Daemon stopped")
        sys.exit(0)


if __name__ == '__main__':
    main()
