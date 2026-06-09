import base64
import ctypes
import io
import json
import logging
import time
from typing import Dict, Any, List, Optional
from PIL import ImageGrab

# Set Process DPI Aware so coordinates map 1:1 with screenshot pixels on Windows
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

logger = logging.getLogger(__name__)

# Virtual keycode map
KEY_MAP = {
    "enter": 0x0D,
    "tab": 0x09,
    "backspace": 0x08,
    "escape": 0x1B,
    "space": 0x20,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "pgup": 0x21,
    "pgdn": 0x22,
    "home": 0x24,
    "end": 0x23,
    "delete": 0x2E,
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,
    "win": 0x5B,
    "ctrl": 0x11,
    "alt": 0x12,
    "shift": 0x10,
}

# Ctypes structures for SendInput keyboard simulation
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_ushort),
        ("wParamH", ctypes.c_ushort)
    ]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]

class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("ki", KEYBDINPUT),
        ("mi", MOUSEINPUT),
        ("hi", HARDWAREINPUT)
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("union", INPUT_UNION)
    ]

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

def get_screen_size() -> tuple:
    width = ctypes.windll.user32.GetSystemMetrics(0)
    height = ctypes.windll.user32.GetSystemMetrics(1)
    return width, height

async def take_screenshot() -> Dict[str, Any]:
    # Capture the screen using PIL ImageGrab
    img = ImageGrab.grab()
    # Resize slightly if too large to conserve token budget
    # Keep the size but compress it using high-quality JPEG
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=80)
    b64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
    
    return {
        "images": [{
            "mimeType": "image/jpeg",
            "data": b64_data
        }],
        "output": f"Screenshot captured. Screen size: {img.width}x{img.height}.",
        "exit_code": 0
    }

async def do_computer_action(args_json: str) -> Dict[str, Any]:
    try:
        args = json.loads(args_json) if isinstance(args_json, str) else args_json
    except Exception as e:
        return {"error": f"Failed to parse arguments: {e}", "exit_code": 1}
        
    action = args.get("action")
    if not action:
        return {"error": "Missing 'action' parameter", "exit_code": 1}
        
    logger.info(f"Executing computer action: {action}")
    
    # 1. SCREENSHOT
    if action == "screenshot":
        return await take_screenshot()
        
    # Mouse helper functions
    def move_to(coord):
        if not coord or not isinstance(coord, list) or len(coord) < 2:
            raise ValueError("Coordinate [x, y] required for this action")
        x, y = int(coord[0]), int(coord[1])
        ctypes.windll.user32.SetCursorPos(x, y)
        time.sleep(0.05)
        return x, y
        
    # 2. MOUSE MOVE
    if action == "mouse_move":
        try:
            x, y = move_to(args.get("coordinate"))
            return {"output": f"Mouse moved to {x}, {y}", "exit_code": 0}
        except Exception as e:
            return {"error": str(e), "exit_code": 1}
            
    # 3. LEFT CLICK
    if action == "left_click":
        try:
            coord = args.get("coordinate")
            if coord:
                move_to(coord)
            # Left down & up
            ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
            time.sleep(0.05)
            ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
            return {"output": "Left clicked", "exit_code": 0}
        except Exception as e:
            return {"error": str(e), "exit_code": 1}
            
    # 4. RIGHT CLICK
    if action == "right_click":
        try:
            coord = args.get("coordinate")
            if coord:
                move_to(coord)
            # Right down & up
            ctypes.windll.user32.mouse_event(0x0008, 0, 0, 0, 0)
            time.sleep(0.05)
            ctypes.windll.user32.mouse_event(0x0010, 0, 0, 0, 0)
            return {"output": "Right clicked", "exit_code": 0}
        except Exception as e:
            return {"error": str(e), "exit_code": 1}
            
    # 5. DOUBLE CLICK
    if action == "double_click":
        try:
            coord = args.get("coordinate")
            if coord:
                move_to(coord)
            # Two clicks
            ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
            time.sleep(0.05)
            ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
            time.sleep(0.1)
            ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
            time.sleep(0.05)
            ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
            return {"output": "Double clicked", "exit_code": 0}
        except Exception as e:
            return {"error": str(e), "exit_code": 1}
            
    # 6. LEFT CLICK DRAG
    if action == "left_click_drag":
        try:
            coord = args.get("coordinate")
            if not coord or not isinstance(coord, list) or len(coord) < 2:
                return {"error": "Target coordinate [x, y] required", "exit_code": 1}
            x2, y2 = int(coord[0]), int(coord[1])
            # Left down, move, release
            ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
            time.sleep(0.1)
            ctypes.windll.user32.SetCursorPos(x2, y2)
            time.sleep(0.1)
            ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
            return {"output": f"Mouse dragged to {x2}, {y2}", "exit_code": 0}
        except Exception as e:
            return {"error": str(e), "exit_code": 1}
            
    # 7. TYPE TEXT
    if action == "type":
        text = args.get("text")
        if not text:
            return {"error": "Missing 'text' parameter", "exit_code": 1}
        try:
            # Type each unicode character
            for char in text:
                # Press
                ki_down = KEYBDINPUT(0, ord(char), KEYEVENTF_UNICODE, 0, None)
                inp_down = INPUT(INPUT_KEYBOARD, INPUT_UNION(ki=ki_down))
                ctypes.windll.user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(INPUT))
                # Release
                ki_up = KEYBDINPUT(0, ord(char), KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, None)
                inp_up = INPUT(INPUT_KEYBOARD, INPUT_UNION(ki=ki_up))
                ctypes.windll.user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(INPUT))
                time.sleep(0.01)
            return {"output": f"Typed text: {text}", "exit_code": 0}
        except Exception as e:
            return {"error": f"Failed to type: {e}", "exit_code": 1}
            
    # 8. SPECIAL KEY
    if action == "key":
        key_name = args.get("key")
        if not key_name:
            return {"error": "Missing 'key' parameter", "exit_code": 1}
            
        # If it's a combination (like ctrl+c or win+r)
        if "+" in key_name:
            parts = key_name.split("+")
            try:
                # Convert parts to virtual key codes
                vks = []
                for p in parts:
                    p_clean = p.strip().lower()
                    if p_clean in KEY_MAP:
                        vks.append(KEY_MAP[p_clean])
                    elif len(p_clean) == 1:
                        vk = ctypes.windll.user32.VkKeyScanW(ord(p_clean)) & 0xFF
                        vks.append(vk)
                    else:
                        return {"error": f"Unknown key in combination: {p_clean}", "exit_code": 1}
                # Press keys in order
                for vk in vks:
                    ki = KEYBDINPUT(vk, 0, 0, 0, None)
                    inp = INPUT(INPUT_KEYBOARD, INPUT_UNION(ki=ki))
                    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
                time.sleep(0.05)
                # Release keys in reverse order
                for vk in reversed(vks):
                    ki = KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP, 0, None)
                    inp = INPUT(INPUT_KEYBOARD, INPUT_UNION(ki=ki))
                    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
                return {"output": f"Pressed combination: {key_name}", "exit_code": 0}
            except Exception as e:
                return {"error": f"Failed to press key combination: {e}", "exit_code": 1}
        else:
            vk = KEY_MAP.get(key_name.lower())
            if not vk:
                return {"error": f"Unknown key: {key_name}", "exit_code": 1}
            try:
                # Press
                ki_down = KEYBDINPUT(vk, 0, 0, 0, None)
                inp_down = INPUT(INPUT_KEYBOARD, INPUT_UNION(ki=ki_down))
                ctypes.windll.user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(INPUT))
                time.sleep(0.05)
                # Release
                ki_up = KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP, 0, None)
                inp_up = INPUT(INPUT_KEYBOARD, INPUT_UNION(ki=ki_up))
                ctypes.windll.user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(INPUT))
                return {"output": f"Pressed key: {key_name}", "exit_code": 0}
            except Exception as e:
                return {"error": f"Failed to press key: {e}", "exit_code": 1}
                
    return {"error": f"Unknown action: {action}", "exit_code": 1}
