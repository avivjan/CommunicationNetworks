from pyexpat.errors import messages
from typing import Tuple

import cman_utils
from cman_game_map import read_map
import socket
import time
import argparse

KEYS_TO_HOOK = ['w', 'a', 's', 'd', 'q']
QUIT_MESSAGE = 'q'
DIRECTION_MAP = {'w': 0, 'a': 1, 's': 2, 'd': 3}
ROLES = {'watcher': 0, 'cman': 1, 'spirit': 2}

GAME_UPDATE_OPCODE = 0x80
GAME_END_OPCODE = 0x8F
ERROR_OPCODE = 0xFF
# Get the current map, update the map and print it
map_data = read_map("map.txt")

def receive_server_message(message: bytes):
    """

    :param message: The message to unpack
    :return:
    """
    opcode = message[0]


    # Game state update
    if opcode == GAME_UPDATE_OPCODE:
        return handle_game_state_update(message)

    # Game end
    elif opcode == GAME_END_OPCODE:
        handle_game_end(message)

    # Error
    elif opcode == ERROR_OPCODE:
        handle_error(message)
        pass


def handle_game_state_update(message: bytes) -> bool:

    global map_data
    # If this game state update than check if value is 1 if so than can move will be True else false
    can_move = message[1] == 0
    cman_coords = (message[2], message[3])
    spirit_coords = (message[4], message[5])
    attempts = message[6]
    collected = message[7:12]

    map_data = update_map(map_string=map_data, pacman_pos=cman_coords, ghost_pos=spirit_coords)
    cman_utils.clear_print()
    print_pacman_map()

def handle_game_end(message: bytes):
    cman_won = message[1] == 1
    cman_num_caught = message[2]
    cman_points_collected = message[3]

    winner = "cman" if cman_won else "spirit"
    print(f"Winner is: {winner}\nSpirit score: {cman_num_caught}\nCman scroe: {cman_points_collected}")

def handle_error(message: bytes):
    error_data = message[1:12]
    print(f"Error is: {error_data}")

def send_join_message(sock: socket.socket, server_address: tuple, role: int):
    join_message = bytes([0x00, role])
    sock.sendto(join_message, server_address)


def send_quit_message(sock: socket.socket, server_address: tuple):
    """
    Sends a quit message to the server.
    :param sock: The socket object used to communicate with the server.
    :param server_address: The server's IP address and port.
    """
    quit_message = bytes([0x0F])
    sock.sendto(quit_message, server_address)
    print("Quit message sent to server.")


def send_move_message(sock: socket.socket, server_address: Tuple, direction: int):
    """
    :param sock: The socket object used to communicate with the server.
    :param server_address: The server's IP address and port.
    :param direction: The direction the player chose to go.
    :return:
    """
    move_message = bytes([0x01, direction])
    sock.sendto(move_message, server_address)

def wait_for_move_confirmation(sock: socket.socket):
    print("Waiting for move confirmation")
    can_move = False
    while not can_move:
        data, _ = sock.recvfrom(1024)
        # If message is not game state update
        if data[0] != GAME_UPDATE_OPCODE:
            continue
        can_move = data[1] == 0
    print("Got move confirmation")

def handle_get_update(sock: socket.socket):
    # Listen for server updates
    try:
        sock.settimeout(0.1)  # Non-blocking wait
        data, _ = sock.recvfrom(1024)
        print(f"Server response: {data}")
    except socket.timeout:
        pass  # No data received within the timeout
    return data


def update_map(map_string, pacman_pos=None, ghost_pos=None):
    """
    Updates the map with new positions for Pacman (C) and Ghost (S).

    Args:
        map_string (str): The map string to process.
        pacman_pos (tuple): The new position of Pacman as (row, col), optional.
        ghost_pos (tuple): The new position of Ghost as (row, col), optional.

    Returns:
        str: The updated map string.
    """
    # Convert the map string into a list of rows for easier manipulation
    rows = map_string.split('\n')

    # Update Pacman position if provided
    if pacman_pos:
        old_row = [row for row in rows if 'C' in row]
        if old_row:
            old_row_idx = rows.index(old_row[0])
            old_col_idx = old_row[0].index('C')
            rows[old_row_idx] = rows[old_row_idx][:old_col_idx] + 'F' + rows[old_row_idx][old_col_idx + 1:]
        row, col = pacman_pos
        rows[row] = rows[row][:col] + 'C' + rows[row][col + 1:]

    # Update Ghost position if provided
    if ghost_pos:
        old_row = [row for row in rows if 'S' in row]
        if old_row:
            old_row_idx = rows.index(old_row[0])
            old_col_idx = old_row[0].index('S')
            rows[old_row_idx] = rows[old_row_idx][:old_col_idx] + 'F' + rows[old_row_idx][old_col_idx + 1:]
        row, col = ghost_pos
        rows[row] = rows[row][:col] + 'S' + rows[row][col + 1:]

    # Join rows back into a string
    return '\n'.join(rows)


def print_pacman_map():
    """ Function that prints the current game map """
    # Split the map string into rows
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


def main():
    global map_data

    # Argument parsing
    parser = argparse.ArgumentParser(description="Cman Game Client")
    parser.add_argument("role", choices=["cman", "spirit", "watcher"], help="Role to play: cman, spirit, or watcher.")
    parser.add_argument("addr", help="Server address (IP or hostname).")
    parser.add_argument("-p", "--port", type=int, default=1337, help="Server port (default: 1337).")
    args = parser.parse_args()

    # Extract arguments
    role = args.role
    server_address = (args.addr, args.port)

    # Create a UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    print(f"Client started with role: {role}. Connecting to {server_address}. Press 'q' to quit.")

    try:
        # Send join message
        send_join_message(sock, server_address, ROLES[role])

        # In case of watcher it is 0 otherwise 1 or 2
        if ROLES[role]:
            wait_for_move_confirmation(sock)



        while True:
            # Check for pressed keys
            keys = cman_utils.get_pressed_keys(keys_filter=KEYS_TO_HOOK)

            if keys:
                if QUIT_MESSAGE in keys:
                    # Handle quit
                    send_quit_message(sock, server_address)
                    break

                # Check for update from server and update accordingly
                update_message = handle_get_update(sock)
                if update_message:
                    receive_server_message(update_message)
                    if update_message != GAME_UPDATE_OPCODE:
                        sock.close()
                        exit()

                # Map key presses to directions and send to server
                for key in keys:
                    if key in DIRECTION_MAP:
                        send_move_message(sock, server_address, DIRECTION_MAP[key])
                        print(f"Sent move: {key}")


            # Add a short delay
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Exiting due to user interrupt.")
    finally:
        sock.close()


if __name__ == '__main__':
    main()
