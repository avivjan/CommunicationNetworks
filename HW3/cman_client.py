from typing import Tuple
import socket
import argparse
import select
import cman_utils
from cman_game_map import read_map
import threading
from cman_utils import key_listener
from cman_utils import pressed_keys as key_queue
import signal

KEYS_TO_HOOK = ['w', 'a', 's', 'd', 'q']
QUIT_MESSAGE = 'q'
DIRECTION_MAP = {'w': 0, 'a': 1, 's': 2, 'd': 3}
ROLES = {'watcher': 0, 'cman': 1, 'spirit': 2}

GAME_UPDATE_OPCODE = 0x80
GAME_END_OPCODE = 0x8F
ERROR_OPCODE = 0xFF

# Global variables
map_data = read_map("map.txt")
last_message = b""
points = {}  # Track all points on the map
last_ghost_pos = None  # Track the Ghost's previous position
server_address = None
sock = None


def initialize_points(map_string):
    """
    Initializes the points dictionary by scanning the map for all point locations.
    """
    global points
    rows = map_string.split('\n')
    points = {(r_idx, c_idx): True for r_idx, row in enumerate(rows) for c_idx, char in enumerate(row) if char == 'P'}


def update_map(map_string, pacman_pos=None, ghost_pos=None, prev_ghost_pos=None):
    """
    Updates the map with new positions for Pacman ('C') and Ghost ('S'),
    ensuring Pacman collects points and Ghost restores points when moving away.

    Args:
        map_string (str): The current map as a string.
        pacman_pos (tuple): New position for Pacman as (row, col), optional.
        ghost_pos (tuple): New position for Ghost as (row, col), optional.
        prev_ghost_pos (tuple): Previous position of the Ghost, used for restoring points.

    Returns:
        str: Updated map string.
    """
    global points

    rows = map_string.split('\n')

    # Restore the point if the Ghost moved away from a point
    if prev_ghost_pos and prev_ghost_pos in points:
        r, c = prev_ghost_pos
        rows[r] = rows[r][:c] + 'P' + rows[r][c + 1:]

    # Clear Pacman's old position
    if pacman_pos:
        for r_idx, row in enumerate(rows):
            if 'C' in row:
                c_idx = row.index('C')
                rows[r_idx] = row[:c_idx] + 'F' + row[c_idx + 1:]
                break

    # Clear Ghost's old position
    if ghost_pos:
        for r_idx, row in enumerate(rows):
            if 'S' in row:
                c_idx = row.index('S')
                rows[r_idx] = row[:c_idx] + 'F' + row[c_idx + 1:]
                break

    # Update Pacman's position
    if pacman_pos:
        r, c = pacman_pos
        if pacman_pos in points:
            del points[pacman_pos]  # Pacman collects the point
        rows[r] = rows[r][:c] + 'C' + rows[r][c + 1:]

    # Update Ghost's position
    if ghost_pos:
        r, c = ghost_pos
        rows[r] = rows[r][:c] + 'S' + rows[r][c + 1:]

    return '\n'.join(rows)


def print_pacman_map(attempts, collected):
    """ Function that prints the current game map """
    rows = map_data.split('\n')

    # Define a legend for better readability
    legend = {
        'W': '█',  # Wall
        'F': ' ',  # Free space
        'P': '.',  # Dot
        'C': 'C',  # Pacman
        'S': 'S'  # Ghost
    }

    # Convert each row using the legend
    for row in rows:
        print(''.join(legend[char] for char in row))

    print(f'\nAttempts left: {attempts}\nCollected points: {collected}')


def print_game_map_to_screen(attempts, collected):
    global map_data
    cman_utils.clear_print()
    print_pacman_map(attempts, collected)


def receive_server_message(message: bytes):
    """
    Processes a message from the server.
    """
    opcode = message[0]


    if opcode == GAME_UPDATE_OPCODE:
        handle_game_state_update(message)
    elif opcode == GAME_END_OPCODE:
        handle_game_end(message)
        return True
    elif opcode == ERROR_OPCODE:
        return handle_error(message)
    else:
        print(f"Unknown opcode received: {opcode}")


def handle_game_state_update(message: bytes):
    """
    Handles game state updates and updates the map accordingly.
    """
    global map_data, last_ghost_pos

    # Extract game state details
    can_move = message[1] == 0
    pacman_coords = (message[2], message[3])
    ghost_coords = (message[4], message[5])
    attempts = 3 - message[6]
    collected = decode_and_count_ones(message[7:])

    # Update the map
    try:
        map_data = update_map(
            map_string=map_data,
            pacman_pos=pacman_coords,
            ghost_pos=ghost_coords,
            prev_ghost_pos=last_ghost_pos
        )
        last_ghost_pos = ghost_coords  # Update the Ghost's last position
        print_game_map_to_screen(attempts, collected)
    except ValueError as e:
        print(f"Error updating map: {e}")


def handle_game_end(message: bytes):
    cman_won = message[1] == 1
    cman_num_caught = message[2]
    cman_points_collected = message[3]

    winner = "cman" if cman_won else "spirit"
    print(f"Winner is: {winner}\nSpirit score: {cman_num_caught}\nCman score: {cman_points_collected}")


def handle_error(message: bytes):
    error_data = message[1:12]
    error_data = error_data.decode('utf-8')
    if error_data == "0":
        print("Player cannot move in this state of the game")
        return False
    if error_data == "1":
        print("invalid join message")
        return True        
    if error_data == "2":
        print("User already joined")
        return True   
    if error_data == "3":
        print("Active player cant join - Game already started")
        return True   
    if error_data == "4":
        print("Cman cant join - already occupied")
        return True   
    if error_data == "5":
        print("Spirit cant join - already occupied")
        return True   
    if error_data == "6":
        print("Cant join -  Invalid role")
        return True   
    if error_data == "7":
        print("movement detected from an unknown user")
        return True   
    if error_data == "8":
        print("Invalid movement message")
        return False   
    if error_data == "9":
        print("Invalid direction in movement message")
        return False   
    if error_data == "10":
        print("Watcher can't move")
        return False   
    if error_data == "11":
        print("Quit message or timedout from unknown user")
        return True
    if error_data == "12":
        print("Invalid quit message: should be only opcode")
        return True   
    else:
        print("Unknown error")
        return True

def send_join_message(role: int):
    global sock, server_address
    join_message = bytes([0x00, role])
    sock.sendto(join_message, server_address)


def send_quit_message(signum=None, frame=None):
    global sock, server_address
    quit_message = bytes([0x0F])
    sock.sendto(quit_message, server_address)
    print("Quit message sent to server.")
    exit(0)
    


def send_move_message(direction: int):
    global sock, server_address
    move_message = bytes([0x01, direction])
    sock.sendto(move_message, server_address)


def decode_and_count_ones(encoded_points):
    integer_value = int.from_bytes(encoded_points, byteorder='big')
    binary_string = bin(integer_value)[2:].zfill(40)  # Ensure it's 40 bits long
    ones_count = binary_string.count('1')
    return ones_count

def set_signal_handlers():
    signal.signal(signal.SIGINT, send_quit_message)  
    signal.signal(signal.SIGTERM, send_quit_message)
    signal.signal(signal.SIGHUP, send_quit_message) 
def main():
    set_signal_handlers()
    global map_data, points, last_ghost_pos, server_address, sock

    # Argument parsing
    parser = argparse.ArgumentParser(description="Cman Game Client")
    parser.add_argument("role", choices=["cman", "spirit", "watcher"], help="Role to play: cman, spirit, or watcher.")
    parser.add_argument("addr", help="Server address (IP or hostname).")
    parser.add_argument("-p", "--port", type=int, default=1337, help="Server port (default: 1337).")
    args = parser.parse_args()

    role = args.role
    server_address = (args.addr, args.port) 
    

    # Initialize points dictionary
    initialize_points(map_data)

    # Create a UDP socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    key_thread = threading.Thread(target=key_listener, args=(KEYS_TO_HOOK,), daemon=True)
    key_thread.start()

    print("connecting to server...")

    try:
        send_join_message(ROLES[role])

        while True:
            # Process server updates
            readable, _, _ = select.select([sock], [], [], 0.05)
            if sock in readable:
                data, _ = sock.recvfrom(1024)
                if receive_server_message(data):
                    break

            # Check for user input
            while not key_queue.empty():
                key = key_queue.get()
                if key == QUIT_MESSAGE:
                    send_quit_message()

                if key in DIRECTION_MAP:
                    send_move_message(DIRECTION_MAP[key])

    except KeyboardInterrupt:
        send_quit_message()
        print("Exiting due to user interrupt.")
    except Exception as e:
        print(f"Exception: {e}")
    finally:
        sock.close()


if __name__ == '__main__':
    main()
