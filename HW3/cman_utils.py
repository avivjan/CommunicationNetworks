import sys
import pynput, time

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


def get_pressed_keys(keys_filter = None):
    """
    
    Returns a list of all pressed keys at the time of the call.

    Parameters:

    keys_filter (list[str]): A list of specific keys to check. If omitted, every key is checked.

    Returns:

    list[str]: A list of currently pressed keys.

    """
    keys_lst = []
    def on_press(key):
        try:
            if key.char not in keys_lst:
                keys_lst.append(key.char)
        except AttributeError:
            if key not in keys_lst:
                keys_lst.append(str(key))
    listener = pynput.keyboard.Listener(on_press=on_press)
    listener.start()
    time.sleep(0.33)
    listener.stop()
    _flush_input()
    if keys_filter is None:
        return keys_lst
    else:
        return [k for k in keys_filter if k in keys_lst]

def clear_print(*args, **kwargs):
    """

    Clears the terminal before calling print()

    """
    print("\033[H\033[J", end="")
    print(*args, **kwargs)
