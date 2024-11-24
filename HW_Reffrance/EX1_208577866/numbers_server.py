#!/usr/bin/python3

import sys
from socket import *
import select

# SERVER SIDE

client_sockets_dict = {}
client_credentials_set = set()


def main():
    DEFAULT_PORT = 1337
    num_params = len(sys.argv)

    # Check if users_file and port number provided
    if num_params == 3 and sys.argv[2].isnumeric():
        init_server(sys.argv[1], int(sys.argv[2]))

    # Check if users_file provided
    elif num_params == 2:
        init_server(sys.argv[1], DEFAULT_PORT)

    # Error in provided arguments
    else:
        print("Error: Arguments not provided in correct format")
        sys.exit(1)


def init_server(users_file_path, port):
    try:
        # Read users_file and save the data in a set
        with open(users_file_path, 'r') as file:
            for line in file:
                if not line.strip():
                    continue
                username, password = line.strip().split()
                client_credentials_set.add(f"{username} {password}")

        # Init the server and listen to clients
        with socket(AF_INET, SOCK_STREAM) as server_socket:
            server_socket.bind(('', port))
            server_socket.listen(5)
            readable_sockets = [server_socket]
            writable_sockets = []
            while True:
                try:
                    readable, writable, _ = select.select(readable_sockets, writable_sockets, [])
                    for soc in readable:
                        if soc is server_socket:
                            # Accepts new clients if soc is the listening socket
                            client_socket, _ = soc.accept()
                            readable_sockets.append(client_socket)
                            writable_sockets.append(client_socket)
                            client_sockets_dict[client_socket] = {'status': 'auth required', 'buffer': b''}
                        else:
                            # Receive request from client
                            data = soc.recv(1024)
                            if not data:
                                disconnect_client(readable_sockets, writable_sockets, soc)
                                continue
                            client_sockets_dict[soc]['buffer'] += data
                            
                            if b'#' in client_sockets_dict[soc]['buffer']:

                                # Split to request size and request data
                                request_size_in_bytes, request_in_bytes = client_sockets_dict[soc]['buffer'].split(b'#', 1)
                                request_size = to_number(request_size_in_bytes.decode())

                                # Check if request fully received
                                if request_size == len(request_in_bytes):
                                    client_sockets_dict[soc]['buffer'] = b''
                                    client_request = request_in_bytes.decode()
                                    # Handle request
                                    handle_readable(client_request, soc)

                                # Check if request is bigger than expected
                                elif request_size < len(request_in_bytes):
                                    disconnect_client(readable_sockets, writable_sockets, soc)

                    for soc in writable:
                        # process client request
                        response = handle_writable(soc)

                        # Check if an error occured
                        if not response:
                            disconnect_client(readable_sockets, writable_sockets, soc, True)

                        # Check and send response if it was processed successfully
                        elif response != 'match nothing':
                            send_all(soc, f"{len(response)}#{response}".encode())
                except Exception as e:
                    disconnect_client(readable_sockets, writable_sockets, soc)

    except Exception as e:
        print(e)
        for client_socket in client_sockets_dict.keys():
            try:
                client_socket.close()
            except:
                print("Client is disconnected")
        


def disconnect_client(readable_sockets: list, writable_sockets: list, client_socket: socket):
    if client_socket in client_sockets_dict:
        del client_sockets_dict[client_socket]

    if client_socket in readable_sockets:
        readable_sockets.remove(client_socket)

    if client_socket in writable_sockets:    
        writable_sockets.remove(client_socket)
    try:
        client_socket.close()
    except:
        print("Client is disconnected")


def handle_readable(client_data, client_socket: socket):
    try:
        status = client_sockets_dict[client_socket]['status']

        if status == 'username format check':
            username = assert_input_format(client_data, client_socket, 'User:')
            if username:
                client_sockets_dict[client_socket]["status"] = 'valid username format'
                client_sockets_dict[client_socket]["user_data"] = username
            return

        elif status == 'password format check and handle auth':
            password = assert_input_format(client_data, client_socket, 'Password:')
            if password:
                username = client_sockets_dict[client_socket]['user_data']
                handle_authentication(username, password, client_socket)
            return

        elif status == 'handle service':
            func_name, params = client_data.split(':')
            response = handle_service(func_name, params)
            client_sockets_dict[client_socket]['user_data'] = response
            client_sockets_dict[client_socket]['status'] = 'send response'
            return
        else:
            return

    except Exception as e:
        print(e)
        client_sockets_dict[client_socket]['status'] = 'error'
        return


def handle_writable(client_socket: socket):
    try:
        status = client_sockets_dict[client_socket]['status']

        if status == 'auth required':
            client_sockets_dict[client_socket]['status'] = 'username format check'
            return "Welcome! Please log in."

        elif status == 'valid username format':
            client_sockets_dict[client_socket]['status'] = 'password format check and handle auth'
            return "Username format is valid"

        elif status == 'failed login':
            client_sockets_dict[client_socket]['status'] = 'username format check'
            return "Failed to login."

        elif status == 'successful login':
            username = client_sockets_dict[client_socket]["user_data"]
            client_sockets_dict[client_socket]['status'] = 'handle service'
            return f"Hi {username}, good to see you."

        elif status == 'send response':
            response = client_sockets_dict[client_socket]["user_data"]
            if response != None:
                client_sockets_dict[client_socket]['status'] = 'handle service'
                return f"response: {response}."
            raise Exception("Sent error message to client")

        elif status == 'error':
            raise Exception("Sent error message to client")

        else:
            return "match nothing"

    except Exception as e:
        print(e)
        send_all(client_socket, f"{len('An error occured')}#An error occured".encode())
        client_sockets_dict[client_socket]['status'] = 'match nothing'
        return None

def assert_input_format(string: str, client_socket: socket, expected_format_prefix: str):
    try: 
        format_prefix, string_value = string.split()
        string_value = string_value.strip()

        if format_prefix != expected_format_prefix:
            raise Exception('error')
        return string_value

    except:
        client_sockets_dict[client_socket]["status"] = 'error'
        return None

def handle_authentication(username, password, client_socket: socket):
    try:
        if f"{username} {password}" in client_credentials_set:
            client_sockets_dict[client_socket]["status"] = 'successful login'
            client_sockets_dict[client_socket]["user_data"] = username
            return
        raise
    except:
        client_sockets_dict[client_socket]["status"] = 'failed login'
        return

def handle_service(func_name, params):
    try:
        if func_name == 'calculate':
            num1, op, num2 = params.split()
            return calculate(to_number(num1), op, to_number(num2))

        elif func_name == 'is_palindrome':
            params = params.strip()
            to_number(params)
            return is_palindrome(params)

        elif func_name == 'is_primary':
            params = params.strip()
            return is_primary(to_number(params))
        return None

    except:
        return None


def calculate(num1, op, num2):
    if op == '+':
        return num1 + num2
    elif op == '-':
        return num1 - num2
    elif op == 'x':
        return num1 * num2
    elif op == '/':
        return round(num1 / num2, 2)
    return None


def is_palindrome(num):
    return "Yes" if num == num[::-1] else "No"


def is_primary(num):
    if num == 2 or num == 3:
        return "Yes"
    if num < 0 or num == 1 or num % 2 == 0 or num % 3 == 0:
        return "No"
    max_divisor = int(num ** 0.5) + 1
    for i in range(3, max_divisor, 2):
        if num % i == 0:
            return "No"
    return "Yes"

def send_all(client_socket: socket, encoded_data):
    total = 0
    while total < len(encoded_data):
        bytes_sent = client_socket.send(encoded_data[total:])
        if bytes_sent == 0:
            break
        total += bytes_sent
    return total

def to_number(num):
    return int(num)

if __name__ == "__main__":
    main()
