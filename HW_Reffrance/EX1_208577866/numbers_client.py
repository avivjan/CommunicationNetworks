#!/usr/bin/python3

import sys
from socket import *

## CLIENT SIDE

def main():
    DEFAULT_HOST = "localhost"
    DEFAULT_PORT = 1337
    num_params = len(sys.argv)

    # Check if hostname and port number arguments provided
    if num_params == 3 and sys.argv[2].isnumeric():
        init_client_session(sys.argv[1], int(sys.argv[2]))

    # Check if hostname argument provided
    elif num_params == 2 and not sys.argv[1].isnumeric():
        init_client_session(sys.argv[1], DEFAULT_PORT)

    # Check if no aruments provided
    elif num_params == 1:
        init_client_session(DEFAULT_HOST, DEFAULT_PORT)

    # Error in provided arguments
    else:
        print("Error: Arguments not provided in correct format")
        sys.exit(1)


def init_client_session(hostname, port):
    try:
        with socket(AF_INET, SOCK_STREAM) as client_socket:
            client_socket.connect((hostname, port))

            # Receive and print welcome message
            initial_server_message = recv_server_response(client_socket)
            if not initial_server_message:
                return
            print(initial_server_message)

            # Start authentication process
            auth_status = handle_authentication(client_socket)
            if not auth_status:
                return
            
            # Request service from server
            while True:

                # Get service from client
                service = input()

                if service == "quit":
                    break
                # Send service to server
                send_all(client_socket, f"{len(service)}#{service}".encode())

                # Receive response of service from server
                response = recv_server_response(client_socket)
                if not response:
                    break
                print(response)

                # Check if there was an error in the last service request
                if 'response:' not in response:
                    break

    except Exception as e:
        print(e)


def handle_authentication(client_socket: socket):
    while True:
        # Get username from client and send to server
        username = input()
        send_all(client_socket, f"{len(username)}#{username}".encode())

        # Receive a username format message: successful | error
        response = recv_server_response(client_socket)
        if response == 'An error occured':
            print(response)
            return None

        # Get password from client and send to server
        password = input()
        send_all(client_socket, f"{len(password)}#{password}".encode())

        # Receive a login message: successful | failed | error
        response = recv_server_response(client_socket)
        print(response)
        if response == 'An error occured':
            return None
        elif response == "Failed to login.":
            continue
        return 200


def send_all(client_socket: socket, encoded_data):
    total = 0
    while total < len(encoded_data):
        bytes_sent = client_socket.send(encoded_data[total:])
        if bytes_sent == 0:
            break
        total += bytes_sent
    return total

def recv_server_response(client_socket: socket):
    response_in_bytes = b''
    while True:
        data = client_socket.recv(1024)
        if not data:
            break
        response_in_bytes += data
        if b'#' in response_in_bytes:
            # Split to response size and response data
            response_size_in_bytes, response_data_in_bytes = response_in_bytes.split(b'#', 1)
            response_size = to_number(response_size_in_bytes.decode())
 
            # Check if response fully received
            if response_size == len(response_data_in_bytes):
                return response_data_in_bytes.decode()
            
            # Check if response is bigger than expected
            elif response_size < len(response_data_in_bytes):
                break
    return None

def to_number(num):
    return int(num)


if __name__ == "__main__":
    main()
