from typing import Tuple

import cman_utils
import socket
import time
import argparse

KEYS_TO_HOOK = ['w', 'a', 's', 'd', 'q']
QUIT_MESSAGE = 'q'
DIRECTION_MAP = {'w': 0, 'a': 1, 's': 2, 'd': 3}
ROLES = {'watcher': 0, 'cman': 1, 'spirit': 2}

def receive_server_message(message: bytes):
    """

    :param message: The message to unpack
    :return:
    """
    opcode = message[0]

    # Game state update
    if opcode == 0x80:
        pass

    # Game end
    elif opcode == 0x8F:
        pass

    # Error
    elif opcode == 0xFF:
        pass



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



def main():
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

        while True:
            # Check for pressed keys
            keys = cman_utils.get_pressed_keys(keys_filter=KEYS_TO_HOOK)

            if keys:
                if QUIT_MESSAGE in keys:
                    # Handle quit
                    send_quit_message(sock, server_address)
                    break

                # Map key presses to directions and send to server

                for key in keys:
                    if key in DIRECTION_MAP:
                        send_move_message(sock, server_address, DIRECTION_MAP[key])
                        print(f"Sent move: {key}")

            # Listen for server updates
            try:
                sock.settimeout(0.1)  # Non-blocking wait
                data, _ = sock.recvfrom(1024)
                print(f"Server response: {data}")
            except socket.timeout:
                pass  # No data received within the timeout

            # Add a short delay
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Exiting due to user interrupt.")
    finally:
        sock.close()


if __name__ == '__main__':
    main()
