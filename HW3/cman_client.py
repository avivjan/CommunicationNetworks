from typing import Tuple
import socket
import argparse
import select
import cman_utils
from cman_game_map import read_map
import threading
from cman_utils import key_listener
from cman_utils import pressed_keys as key_queue 


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


def print_pacman_map(attempts, collected):
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
    print(f"Message from server: {message}")

    if opcode == GAME_UPDATE_OPCODE:
        handle_game_state_update(message)
    elif opcode == GAME_END_OPCODE:
        handle_game_end(message)
        return True
    elif opcode == ERROR_OPCODE:
        handle_error(message)
        return True
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
    attempts = 3 - message[6]
    collected = decode_and_count_ones(message[7:])
    # Update the map
    try:
        map_data = update_map(map_string=map_data, pacman_pos=pacman_coords, ghost_pos=ghost_coords)
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
    print(f"Error received: {error_data}")


def send_join_message(sock: socket.socket, server_address: tuple, role: int):
    join_message = bytes([0x00, role])
    sock.sendto(join_message,server_address)


def send_quit_message(sock: socket.socket, server_address: tuple):
    quit_message = bytes([0x0F])
    sock.sendto(quit_message, server_address)
    print("Quit message sent to server.")


def send_move_message(sock: socket.socket, server_address: Tuple, direction: int):
    move_message = bytes([0x01, direction])
    sock.sendto(move_message, server_address)

def decode_and_count_ones(encoded_points):
    integer_value = int.from_bytes(encoded_points, byteorder='big')
    binary_string = bin(integer_value)[2:].zfill(40)  # Ensure it's 40 bits long
    ones_count = binary_string.count('1')
    return ones_count



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
    
    key_thread = threading.Thread(target=key_listener, args=(KEYS_TO_HOOK,), daemon=True)
    key_thread.start()


    print(f"Client started with role: {role}. Connecting to {server_address}. Press 'q' to quit.")

    try:
        send_join_message(sock, server_address, ROLES[role])

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
                    send_quit_message(sock, server_address)
                    return

                if key in DIRECTION_MAP:
                    send_move_message(sock, server_address, DIRECTION_MAP[key])
                    print(f"Sent move: {key}")

    except KeyboardInterrupt:
        send_quit_message(sock, server_address)
        print("Exiting due to user interrupt.")
    except Exception as e:
        print(f"Exception: {e}")
    finally:
        sock.close()


if __name__ == '__main__':
    main()
