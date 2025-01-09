from typing import Tuple
import socket
import time
import argparse
from queue import Queue
import cman_utils
from cman_game_map import read_map

KEYS_TO_HOOK = ['w', 'a', 's', 'd', 'q']
QUIT_MESSAGE = 'q'
DIRECTION_MAP = {'w': 0, 'a': 1, 's': 2, 'd': 3}
ROLES = {'watcher': 0, 'cman': 1, 'spirit': 2}

GAME_UPDATE_OPCODE = 0x80
GAME_END_OPCODE = 0x8F
ERROR_OPCODE = 0xFF

# Global variables
map_data = read_map("/Users/user/PycharmProjects/NetworkCommunication/HW3/map.txt")
last_message = b""
message_queue = Queue()


def update_map(map_string, pacman_pos=None, ghost_pos=None):
    """
    Updates the map with new positions for Pacman ('C') and Ghost ('S').

    Args:
        map_string (str): The current map as a string.
        pacman_pos (tuple): New position for Pacman as (row, col), optional.
        ghost_pos (tuple): New position for Ghost as (row, col), optional.

    Returns:
        str: Updated map string.
    """
    rows = map_string.split('\n')

    # Helper to clear old positions
    def clear_old_position(rows, char):
        for r_idx, row in enumerate(rows):
            if char in row:
                c_idx = row.index(char)
                rows[r_idx] = row[:c_idx] + 'F' + row[c_idx + 1:]

    # Clear old positions
    if pacman_pos:
        clear_old_position(rows, 'C')
    if ghost_pos:
        clear_old_position(rows, 'S')

    # Update new positions
    def update_position(rows, char, pos):
        if pos:
            row, col = pos
            if 0 <= row < len(rows) and 0 <= col < len(rows[row]):
                rows[row] = rows[row][:col] + char + rows[row][col + 1:]
            else:
                raise ValueError(f"Position {pos} is out of bounds.")

    if pacman_pos:
        update_position(rows, 'C', pacman_pos)
    if ghost_pos:
        update_position(rows, 'S', ghost_pos)

    return '\n'.join(rows)


def print_pacman_map():
    """ Function that prints the current game map """
    rows = map_data.split('\n')

    # Define a legend for better readability
    legend = {
        'W': '█',  # Wall
        'F': ' ',  # Free space
        'P': '.',  # Dot
        'C': 'C',  # Pacman
        'S': 'S'   # Ghost
    }

    # Convert each row using the legend
    for row in rows:
        print(''.join(legend[char] for char in row))


def print_game_map_to_screen():
    global map_data
    cman_utils.clear_print()
    print_pacman_map()


def receive_server_message(message: bytes):
    """
    Processes a message from the server.
    """
    opcode = message[0]
    print(f"Message from server: {message}")

    if opcode == GAME_UPDATE_OPCODE:
        handle_game_state_update(message)
    elif opcode == GAME_END_OPCODE:
        handle_game_end(message)
    elif opcode == ERROR_OPCODE:
        handle_error(message)
    else:
        print(f"Unknown opcode received: {opcode}")


def handle_game_state_update(message: bytes):
    """
    Handles game state updates and updates the map accordingly.
    """
    global map_data

    # Extract game state details
    can_move = message[1] == 0
    pacman_coords = (message[2], message[3])
    ghost_coords = (message[4], message[5])

    # Update the map
    try:
        map_data = update_map(map_string=map_data, pacman_pos=pacman_coords, ghost_pos=ghost_coords)
        print_game_map_to_screen()
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
    print(f"Error received: {error_data}")


def send_join_message(sock: socket.socket, server_address: tuple, role: int):
    join_message = bytes([0x00, role])
    sock.sendto(join_message, server_address)


def send_quit_message(sock: socket.socket, server_address: tuple):
    quit_message = bytes([0x0F])
    sock.sendto(quit_message, server_address)
    print("Quit message sent to server.")


def send_move_message(sock: socket.socket, server_address: Tuple, direction: int):
    move_message = bytes([0x01, direction])
    sock.sendto(move_message, server_address)


def handle_get_update(sock: socket.socket):
    global message_queue

    try:
        sock.settimeout(0.1)
        data, _ = sock.recvfrom(1024)
        message_queue.put(data)
    except socket.timeout:
        pass


def process_message_queue():
    global message_queue

    while not message_queue.empty():
        message = message_queue.get()
        receive_server_message(message)


def main():
    global map_data

    # Argument parsing
    parser = argparse.ArgumentParser(description="Cman Game Client")
    parser.add_argument("role", choices=["cman", "spirit", "watcher"], help="Role to play: cman, spirit, or watcher.")
    parser.add_argument("addr", help="Server address (IP or hostname).")
    parser.add_argument("-p", "--port", type=int, default=1337, help="Server port (default: 1337).")
    args = parser.parse_args()

    role = args.role
    server_address = (args.addr, args.port)

    # Create a UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    print(f"Client started with role: {role}. Connecting to {server_address}. Press 'q' to quit.")

    try:
        send_join_message(sock, server_address, ROLES[role])

        while True:
            print_game_map_to_screen()

            # Process server updates
            handle_get_update(sock)
            process_message_queue()

            # Check for user input
            keys = cman_utils.get_pressed_keys(keys_filter=KEYS_TO_HOOK)
            if keys:
                if QUIT_MESSAGE in keys:
                    send_quit_message(sock, server_address)
                    break

                for key in keys:
                    if key in DIRECTION_MAP:
                        send_move_message(sock, server_address, DIRECTION_MAP[key])
                        print(f"Sent move: {key}")

            time.sleep(0.1)

    except KeyboardInterrupt:
        send_quit_message(sock, server_address)
        print("Exiting due to user interrupt.")
    except Exception as e:
        print(f"Exception: {e}")
    finally:
        sock.close()


if __name__ == '__main__':
    main()
