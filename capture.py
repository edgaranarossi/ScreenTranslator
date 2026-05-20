import mss
from PIL import Image

def get_monitors():
    """Returns a list of available monitors."""
    with mss.mss() as sct:
        # sct.monitors[0] is the bounding box of all monitors
        # sct.monitors[1:] are individual monitors
        return sct.monitors

def capture_screen(capture_mode, custom_area=None):
    """
    Captures the screen based on the given capture_mode.
    capture_mode: "All Desktops", "Monitor 1", "Monitor 2", etc., or "Custom Area".
    custom_area: [x, y, width, height] used if mode is "Custom Area".
    Returns a PIL Image.
    """
    with mss.mss() as sct:
        monitors = sct.monitors
        
        if capture_mode == "All Desktops":
            # Monitor 0 is a bounding box of all monitors
            monitor = monitors[0]
            sct_img = sct.grab(monitor)
            return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            
        elif capture_mode == "Custom Area" and custom_area:
            # custom_area is [x, y, width, height]
            monitor = {
                "top": int(custom_area[1]),
                "left": int(custom_area[0]),
                "width": int(custom_area[2]),
                "height": int(custom_area[3])
            }
            sct_img = sct.grab(monitor)
            return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            
        elif capture_mode.startswith("Monitor "):
            try:
                mon_idx = int(capture_mode.split(" ")[1])
                if mon_idx < len(monitors):
                    monitor = monitors[mon_idx]
                    sct_img = sct.grab(monitor)
                    return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            except ValueError:
                pass
                
        # Fallback to All Desktops if something fails
        monitor = monitors[0]
        sct_img = sct.grab(monitor)
        return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
