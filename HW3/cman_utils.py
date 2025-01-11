import sys
import pynput, time
from queue import Queue
from pynput import keyboard

pressed_keys = Queue()

def _flush_input():
    """
    Clears the input buffer. Works for both Windows and Unix-based systems.
    """
    if not sys.stdin.isatty():
        # If the input is not a terminal, skip flushing
        return
    try:
        import msvcrt
        while msvcrt.kbhit():
            msvcrt.getch()
    except ImportError:
        import termios
        try:
            termios.tcflush(sys.stdin, termios.TCIFLUSH)
        except termios.error:
            pass  # Ignore errors when not in a terminal



def clear_print(*args, **kwargs):
    """

    Clears the terminal before calling print()

    """
    print("\033[H\033[J", end="")
    print(*args, **kwargs)


# Key listener function
def key_listener(keys_filter=None):
    """
    Listens for key presses and adds them to the key queue. Utilizes `_flush_input` to clear stale input.
    """
    def on_press(key):
        try:
            char = key.char  # Get the character of the key
            if keys_filter is None or char in keys_filter:
                if char not in list(pressed_keys.queue):  # Avoid duplicates
                    pressed_keys.put(char)
        except AttributeError:
            pass  # Handle special keys if necessary
    _flush_input()
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()  # Keep the listener running
