import sys
import socket
import select
from Connection import Connection
import csv
import math


MIN_INT32 = -2**31
MAX_INT32 = 2**31 - 1

def main():
    global users_credentials
    global readable_sockets, writable_sockets, connections
    
    # Check the number of arguments
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: ./numbers_server.py users_file [port]")
        print("  users_file: Required argument - path to the user file.")
        print("  port: Optional argument - port number (default is 8080).")
        sys.exit(1)

    # Required argument
    users_credentials = fetch_users_credentials_from_file(sys.argv[1])

    # Optional argument with default
    if len(sys.argv) == 3:
        try:
            port = int(sys.argv[2])
        except ValueError:
            print("Error: Port must be an integer.")
            sys.exit(1)
    else:
        port = 1338  # Default port if not specified
        

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('', port))
    server_socket.listen(10)
    readable_sockets = [server_socket]
    writable_sockets = []
    connections = {}
    
    while True:
        readables, writables, _ = select.select(readable_sockets, writable_sockets, [],0)
        for readable_socket in readables:
            if readable_socket is server_socket:
                client_socket, client_address = server_socket.accept()
                readable_sockets.append(client_socket)
                writable_sockets.append(client_socket)
                connections[client_socket.fileno()] = Connection(client_socket)
            else:
                connection = connections[readable_socket.fileno()]
                if not is_read_mode(connection):
                    continue
                data = readable_socket.recv(1024).decode()
                if not data:
                    disconnect_client(connection)
                    continue
                handle_read(connection, data)
                
        
        for writable_socket in writables:
            if writable_socket.fileno() not in connections:
                continue
            connection = connections[writable_socket.fileno()]
            if not is_write_mode(connection):
                continue
            handle_write(connection)
                
                    
                
                    
                    
                
def is_read_mode(connection):
    return connection.status == 'auth' or connection.status == 'on'

def is_write_mode(connection):
    return connection.status == 'greeting' or connection.status == 'right' or connection.status == 'wrong' or connection.status == 'result'  
        
def send_all(socket, data):
    total_sent = 0
    while total_sent < len(data):
        sent = socket.send(data[total_sent:].encode())
        if sent <= 0: 
            raise RuntimeError("Socket connection broken")
        total_sent += sent

def fetch_users_credentials_from_file(file):
    users = {}
    try :
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
    global users_credentials
    username, password = data.split(',')
    if username not in users_credentials:
        return False
    if users_credentials[username] == password:
        connection.username = username
        return True
    return False


        
def handle_write(connection):
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
        send_all(connection.socket, message)
        connection.read_buffer = ""
        
    connection.status = new_status
        
def handle_read(connection, data):
    connection.read_buffer += data
    if not connection.read_buffer.endswith('\\'):
        disconnect_client(connection)
        return
    else:
        connection.read_buffer = connection.read_buffer[:-1]
        if connection.read_buffer.startswith('4'):
            disconnect_client(connection)
            return
        match connection.status:
            case 'auth':
                if not connection.read_buffer.startswith('0'):
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
                if not (connection.read_buffer.startswith('1') or connection.read_buffer.startswith('2') or connection.read_buffer.startswith('3')):
                    disconnect_client(connection)
                    return
                
                result = execute_command(connection, connection.read_buffer)
                if not result:
                    disconnect_client(connection)
                    return
                connection.read_buffer = result
                connection.status = 'result'
                
                
def execute_command(connection, data):
    if data.startswith('1'):
        data = data[2:]
        num1, op, num2 = data.split()
        return str(calculate(num1=int(num1), op=op, num2=int(num2)))
    if data.startswith('2'):
        return maximum(data[2:])
    if data.startswith('3'):
        return factors(data[2:])
    return None

def calculate(num1, op, num2):
    res = None
    if op == '+':
        res = num1 + num2
    elif op == '-':
        res = num1 - num2
    elif op == 'x':
        res = num1 * num2
    elif op == '/':
        res = round(num1 / num2, 2)
    elif op == '^':
        res = num1 ** num2
    
    if res != math.floor(res):
        res = round(res, 2)
        
    if res > MAX_INT32 or res < MIN_INT32:
        return "error: result is too big"
    return "response: " + str(res) + "." 
    return None


def maximum(data):
    try:
        numbers = data.split(',')
        numbers = [int(number) for number in numbers]
        return "the maximum is " + str(max(numbers))
    except:
        disconnect_client(connection)
        return None
        
def factors(data):
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
        
    except:
        disconnect_client(connection)
        return None
        
                 
                
      
            
            
        
    

if __name__ == "__main__":
    main()
 
    

