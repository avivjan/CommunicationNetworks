import sys
import socket

WELCOME_MESSAGE = "Welcome! Please log in."
USER_NAME = "bob"
PASSWORD = "simplepass"
AUTH_MESSAGE = f"User: {USER_NAME}\nPassword: {PASSWORD}"

def handle_auth(client_socket: socket.socket):
    """ This method is responsible for the authentication of the client against the server """
    resp = client_socket.recv(1024)
    print(resp)

    # Message received from server is auth message
    if resp  == WELCOME_MESSAGE:
        client_socket.sendall(AUTH_MESSAGE.encode())


def execute_command():
    """
    Gets the command from user and parses it.
    If command is valid then it is sent to the server.
    """
    pass

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

        except Exception as e:
            print(f"Could not establish connection to server: {e}")

if __name__ == "__main__":
    main()


