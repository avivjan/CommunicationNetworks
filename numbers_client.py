import re
import sys
import socket

WELCOME_MESSAGE = "Welcome! Please log in."

# Matches on {calculate} at the beginning followed with {space} and then a {signed int} {space} {operation} {signed int}
CALCULATE_COMMAND_REGEX = "^calculate: (-?\d{1,9}) (\^|\/|\*|-|\+) (-?\d{1,9})$"
MAX_COMMAND_REGEX = "^max: \((-?\d+)(?: (-?\d+))*\)$"
FACTORS_COMMAND_REGEX = "^factors: (-?\d+)$"
QUIT = "quit"

MESSAGE_SEP = "\\"

def handle_auth(client_socket: socket.socket):
    """ This method is responsible for the authentication of the client against the server """
    resp = client_socket.recv(1024).decode()
    print(resp)

    # Message received from server is auth message
    if resp  == WELCOME_MESSAGE:
        username = input("User: ")
        password = input("Password: ")
        client_socket.sendall(f"0 {username},{password}{MESSAGE_SEP}".encode())


def execute_command(client_socket: socket.socket):
    """
    Gets the command from user and parses it.
    If command is valid then it is sent to the server.
    """
    command = input("Please enter your command: ")
    if command == QUIT:
        client_socket.sendall(f"4{MESSAGE_SEP}".encode())
        return QUIT

    # if the command is 'calculate' in the correct format then send the parsed arguments
    elif re.match(CALCULATE_COMMAND_REGEX, command):
        command_info_str = " ".join(re.findall(CALCULATE_COMMAND_REGEX, command)[0])
        client_socket.sendall(f"1 {command_info_str}{MESSAGE_SEP}".encode())

    # if the command is max and in the correct format than parse it to format server is expecting
    elif re.match(MAX_COMMAND_REGEX, command):
        command_parsed = command.replace("max: (", "").rstrip(")").replace(" ", ",")
        client_socket.sendall(f"2 {command_parsed}{MESSAGE_SEP}".encode())

    elif re.match(FACTORS_COMMAND_REGEX, command):
        command_parsed = command.replace("factors: ", "")
        client_socket.sendall(f"3 {command_parsed}{MESSAGE_SEP}".encode())

    else:
        print("Got invalid command from user\n Exiting...")
        exit(1)

    resp = client_socket.recv(1024).decode()
    print(resp)


def main():
    # Default values
    default_hostname = "localhost"
    default_port = 1337

    # Parse arguments
    hostname = sys.argv[1] if len(sys.argv) > 1 else default_hostname
    port = int(sys.argv[2]) if len(sys.argv) > 2 else default_port

    # Print the results
    print(f"Connecting to {hostname} on port {port}")

    with socket.socket() as sock:
        try:
            sock.connect((hostname, port))
            handle_auth(sock)
            while True:
                # If we get return value this means we got quit and therefore we should stop
                if execute_command(sock):
                    break

        except Exception as e:
            print(f"Could not establish connection to server: {e}")

if __name__ == "__main__":
    main()


