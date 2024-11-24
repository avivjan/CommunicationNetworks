import sys        # For command-line arguments
import socket     # For network socket operations
import select     # For multiplexing I/O over sockets
from Connection import Connection  # Custom Connection class (assumed to be defined elsewhere)
import csv        # For CSV file handling (imported but not used)
import math       # For mathematical operations

# Define minimum and maximum 32-bit integer values
MIN_INT32 = -2**31
MAX_INT32 = 2**31 - 1

def main():
    # Declare global variables for user credentials and socket connections
    global users_credentials
    global readable_sockets, writable_sockets, connections

    # Check the number of command-line arguments
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: ./numbers_server.py users_file [port]")
        print("  users_file: Required argument - path to the user file.")
        print("  port: Optional argument - port number (default is 8080).")
        sys.exit(1)

    # Load user credentials from the provided file
    users_credentials = fetch_users_credentials_from_file(sys.argv[1])

    # Parse the optional port argument or use default port 1338
    if len(sys.argv) == 3:
        try:
            port = int(sys.argv[2])
        except ValueError:
            print("Error: Port must be an integer.")
            sys.exit(1)
    else:
        port = 1338  # Default port if not specified

    # Create and set up the server socket
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(('', port))
        server_socket.listen(10)
    except socket.error as e:
        print(f"Error: Could not start server on port {port}. {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

    # Initialize lists for readable and writable sockets and a dictionary for connections
    readable_sockets = [server_socket]
    writable_sockets = []
    connections = {}

    # Server loop to handle incoming connections and data
    while True:
        try:
            # Use select to get readable and writable sockets without blocking
            readables, writables, _ = select.select(readable_sockets, writable_sockets, [], 0)
        except select.error as e:
            print(f"Select error: {e}")
            continue
        except Exception as e:
            print(f"Unexpected error during select: {e}")
            continue

        # Handle readable sockets
        for readable_socket in readables:
            if readable_socket is server_socket:
                # Accept new client connections
                try:
                    client_socket, client_address = server_socket.accept()
                    readable_sockets.append(client_socket)
                    writable_sockets.append(client_socket)
                    connections[client_socket.fileno()] = Connection(client_socket)
                except socket.error as e:
                    print(f"Socket accept error: {e}")
                    continue
                except Exception as e:
                    print(f"Unexpected error during accept: {e}")
                    continue
            else:
                # Read data from existing client connections
                try:
                    connection = connections[readable_socket.fileno()]
                    if not is_read_mode(connection):
                        continue
                    data = readable_socket.recv(1024).decode()
                    if not data:
                        disconnect_client(connection)
                        continue
                    handle_read(connection, data)
                except ConnectionResetError:
                    disconnect_client(connection)
                    continue
                except Exception as e:
                    print(f"Error handling read from socket: {e}")
                    disconnect_client(connection)
                    continue

        # Handle writable sockets
        for writable_socket in writables:
            try:
                if writable_socket.fileno() not in connections:
                    continue
                connection = connections[writable_socket.fileno()]
                if not is_write_mode(connection):
                    continue
                handle_write(connection)
            except Exception as e:
                print(f"Error handling write to socket: {e}")
                disconnect_client(connection)
                continue

def is_read_mode(connection):
    # Determine if the connection is ready to read data
    return connection.status == 'auth' or connection.status == 'on'

def is_write_mode(connection):
    # Determine if the connection is ready to write data
    return connection.status in ('greeting', 'right', 'wrong', 'result')  

def send_all(socket, data):
    # Send all data to the client, handling partial sends
    total_sent = 0
    while total_sent < len(data):
        try:
            sent = socket.send(data[total_sent:].encode())
            if sent <= 0: 
                raise RuntimeError("Socket connection broken")
            total_sent += sent
        except socket.error as e:
            raise RuntimeError(f"Socket send error: {e}")

def fetch_users_credentials_from_file(file):
    # Read user credentials from a file and store them in a dictionary
    users = {}
    try:
        with open(file, 'r') as f:
            lines = f.readlines()
            for line in lines:
                username, password = line.split()
                users[username] = password
        return users

    except FileNotFoundError:
        print("Error: File not found.")
        sys.exit(1)
    except ValueError:
        print("Error: Invalid file format.")
        sys.exit(1)

def disconnect_client(connection):
    # Cleanly disconnect a client and remove it from all tracking lists
    global readable_sockets, writable_sockets, connections
    socket = connection.socket
    if socket in readable_sockets:
        readable_sockets.remove(socket)
    if socket in writable_sockets:
        writable_sockets.remove(socket)
    if socket.fileno() in connections:
        del connections[socket.fileno()]
    socket.close()

def authenticate(connection, data):
    # Authenticate a user based on provided credentials
    global users_credentials
    try:
        username, password = data.split(',')
    except ValueError:
        return False
    if username not in users_credentials:
        return False
    if users_credentials[username] == password:
        connection.username = username
        return True
    return False

def handle_write(connection):
    # Handle sending messages to the client based on connection status
    message = ""
    new_status = ""
    match connection.status:
        case 'greeting':
            message = "Welcome! Please log in."
            new_status = 'auth'
        case 'right':
            message = f"Hi {connection.username}, good to see you."
            new_status = 'on'
        case 'wrong':
            message = "N"
            new_status = 'auth'
        case 'result':
            message = connection.read_buffer
            new_status = 'on'

    if message:
        try:
            send_all(connection.socket, message)
        except Exception as e:
            print(f"Error sending data to client: {e}")
            disconnect_client(connection)
            return
        connection.read_buffer = ""

    connection.status = new_status

def handle_read(connection, data):
    # Handle reading data from the client and processing commands
    connection.read_buffer += data
    if not connection.read_buffer.endswith('\\'):
        # Disconnect if the message does not end with the protocol delimiter
        disconnect_client(connection)
        return
    else:
        # Remove the trailing delimiter
        connection.read_buffer = connection.read_buffer[:-1]
        if connection.read_buffer.startswith('4'):
            # Disconnect if the client sends a quit command
            disconnect_client(connection)
            return
        match connection.status:
            case 'auth':
                if not connection.read_buffer.startswith('0'):
                    # Expecting authentication command starting with '0'
                    disconnect_client(connection)
                    return
                success = authenticate(connection, connection.read_buffer[2:])
                if not success:
                    connection.status = 'wrong'
                    connection.read_buffer = ''
                    return
                connection.status = 'right'
                connection.read_buffer = ''

            case 'on':
                if not (connection.read_buffer.startswith('1') or 
                        connection.read_buffer.startswith('2') or 
                        connection.read_buffer.startswith('3')):
                    # Expecting a command starting with '1', '2', or '3'
                    disconnect_client(connection)
                    return

                result = execute_command(connection, connection.read_buffer)
                if not result:
                    disconnect_client(connection)
                    return
                connection.read_buffer = result
                connection.status = 'result'

def execute_command(connection, data):
    # Execute the client's command based on the protocol
    try:
        if data.startswith('1'):
            # Calculate operation
            data = data[2:]
            num1, op, num2 = data.split()
            return str(calculate(num1=int(num1), op=op, num2=int(num2)))
        if data.startswith('2'):
            # Find maximum number
            return maximum(connection, data[2:])
        if data.startswith('3'):
            # Find prime factors
            return factors(connection, data[2:])
        return None
    except Exception as e:
        print(f"Error executing command: {e}")
        return None

def calculate(num1, op, num2):
    # Perform basic arithmetic operations
    try:
        res = None
        if op == '+':
            res = num1 + num2
        elif op == '-':
            res = num1 - num2
        elif op == 'x':
            res = num1 * num2
        elif op == '/':
            if num2 == 0:
                return "error: division by zero"
            res = round(num1 / num2, 2)
        elif op == '^':
            res = num1 ** num2
        else:
            return "error: unknown operation"

        if res != math.floor(res):
            res = round(res, 2)

        if res > MAX_INT32 or res < MIN_INT32:
            return "error: result is too big"
        return "response: " + str(res) + "." 
    except OverflowError:
        return "error: result is too big"
    except ZeroDivisionError:
        return "error: division by zero"
    except Exception as e:
        return f"error: {e}"

def maximum(connection, data):
    # Find the maximum number in a list provided by the client
    try:
        numbers = data.split(',')
        numbers = [int(number) for number in numbers]
        return "the maximum is " + str(max(numbers))
    except Exception as e:
        print(f"Error in maximum function: {e}")
        disconnect_client(connection)
        return None

def factors(connection, data):
    # Calculate the prime factors of a given number
    try:
        n = int(data)
        factors = set()
        divisor = 2

        while n > 1:
            while n % divisor == 0:
                factors.add(divisor)
                n //= divisor
            divisor += 1

            if divisor * divisor > n:
                if n > 1:
                    factors.add(n)
                    break
        factors = sorted(factors)
        return f"the prime factors of {data} are: {str(factors)[1:-1]}"
    except ValueError:
        return None
    except Exception as e:
        print(f"Error in factors function: {e}")
        disconnect_client(connection)
        return None

if __name__ == "__main__":
    main()
