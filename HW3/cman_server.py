import sys
import socket
import json
import argparse
import select
import time
from cman_game import Player, Direction, State, Game

def main():
    global clients, is_cman_occupied, is_spirit_occupied, game, server_socket, last_update_time
    clients = {}
    is_cman_occupied = False
    is_spirit_occupied = False
    game = Game("map.txt")
    
    port = parse_command_line_args().port
    print(f"Server will start on port {port}")
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(('localhost', port))
    server_socket.setblocking(False)  # Non-blocking socket
    
    print("Server started")
    
    last_update_time = time.time()
    
    try:
        while True:
            update_client_game_state_periodically()
            read_sockets, _, _ = select.select([server_socket], [], [], 0.1)
            for sock in read_sockets:
                data, addr = sock.recvfrom(1024)
                data = data.decode()
                opcode = data[0]
                message = data[1:]
                handle_message(opcode, message, addr)
    except KeyboardInterrupt:
        print("Server shutting down gracefully")
        shutdown_server()
    
def update_client_game_state_periodically():
    global last_update_time
    if time.time() - last_update_time > 1.0:
        publish_game_state_update_to_all()
        
        

            
def shutdown_server():
    print("Notifying clients about server shutdown...")
    for client_addr in clients.keys():
        try:
            server_socket.sendto(b'\xFFServer is shutting down.', client_addr)
        except BlockingIOError:
            print(f"Failed to notify {client_addr}: socket buffer is full")
    
    clients.clear()
    server_socket.close()
    print("Server socket closed. Goodbye!")

def parse_command_line_args():
    parser = argparse.ArgumentParser(description="Cman Game Server")
    parser.add_argument("-p", "--port", type=int, default=1337, help="Server port (default: 1337).")
    args = parser.parse_args()
    return args

    args = parser.parse_args()


def handle_message(opcode, message, addr):
    if addr in clients: # we don't want to update last_active for unknown clients
        clients[addr]['last_active'] = time.time()
    if opcode == '\x00':  # 0x00: Join
        handle_join(message, addr)
    elif opcode == '\x01':  # 0x01: Player movement
        handle_player_movement(message, addr)
    elif opcode == '\x0F':  # 0x0F: Quit
        handle_quit(message, addr)

def handle_join(message, addr):
    global is_cman_occupied, is_spirit_occupied
    if len(message) != 1:
        publish_error(addr, "Invalid join message")
        return
    if addr in clients.keys():
        publish_error(addr, "User already joined")
        return
    role = message[0]
    
    if role == '\x00':
        clients[addr] = {'player': Player.NONE, 'last_active': time.time()}
        publish_game_state_update_to_all()
    
    if game.state != State.WAIT:
        publish_error(addr, f"Game has already started, state = {game.state}")
        return
    
    if role == '\x01':
        if is_cman_occupied:
            publish_error(addr, "Cman is already occupied")
            return
        clients[addr] = {'player': Player.CMAN, 'last_active': time.time()}
        is_cman_occupied = True
        if is_spirit_occupied:
            game.next_round()
        publish_game_state_update_to_all()
    elif role == '\x02':
        if is_spirit_occupied:
            publish_error(addr, "Spirit is already occupied")
            return
        clients[addr] = {'player': Player.SPIRIT, 'last_active': time.time()}
        is_spirit_occupied = True
        if is_cman_occupied:
            game.next_round()
        publish_game_state_update_to_all()
    else:
        publish_error(addr, "Invalid role in join message")
        return


def calculate_collected_points():
    points = game.get_points()
    collected_points = ''

    # Build the binary string
    for point in sorted(points.keys()):
        collected_points += str(flip(points[point]))

    # Ensure exactly 40 bits
    collected_points = collected_points.ljust(40, '0')[:40]

    # Convert binary string to 5 bytes
    return int(collected_points, 2).to_bytes(5, byteorder='big')

def flip(bit):
    return 1 if bit == 0 else 0
def handle_player_movement(message, addr): 
    if addr not in clients:
        publish_error(addr, "User not joined")
        return
    if len(message) != 1:
        publish_error(addr, "Invalid movement message")
        return
    direction = message[0]
    if direction not in ['\x00', '\x01', '\x02', '\x03']:
        publish_error(addr, "Invalid direction in movement message")
        return
    if clients[addr]['player'] == Player.NONE:
        publish_error(addr, "Watcher can't move")
        return
    
    direction = int.from_bytes(direction.encode(), byteorder='big')
    print(f"Player {clients[addr]['player']} at {game.cur_coords[clients[addr]['player']]} wants to move {Direction(direction)}")
    game.apply_move(clients[addr]['player'], direction)
    print(f"Player {clients[addr]['player']} moved to {game.cur_coords[clients[addr]['player']]}")
    if game.get_winner() != Player.NONE:
        handle_end_game()
    publish_game_state_update_to_all()

def publish_game_state_update_to_all():
    global last_update_time
    last_update_time = time.time() 
    opcode = b'\x80'
    cman_cor = bytes(game.cur_coords[Player.CMAN])
    spirit_cor = bytes(game.cur_coords[Player.SPIRIT])
    spirit_score = bytes(3 - game.get_game_progress()[0])
    collected_points = calculate_collected_points()
    for client_addr in clients.keys():
        player = clients[client_addr]['player']
        freeze = calc_freeze(player)
        try:
            message = opcode + freeze + cman_cor + spirit_cor + spirit_score + collected_points
            server_socket.sendto(message, client_addr)
            print(f"sending game update with corrdinates: cman: {game.cur_coords[Player.CMAN]}, spirit: {game.cur_coords[Player.SPIRIT]}")
        except BlockingIOError:
            print(f"Failed to send game state update to {client_addr}: socket buffer is full")
def calc_freeze(player):
    if player == Player.NONE:
        return b'\x01'
    else:
        if game.can_move(player):
            return b'\x00'
        else:
            return b'\x01'

def handle_quit(message, addr):
    if addr not in clients:
        publish_error(addr, "Quit message or timedout from unknown user")
        return
    if len(message) != 0:
        publish_error(addr, "Invalid quit message: should be only opcode")
        return
    if clients[addr]['player'] == Player.CMAN:
        global is_cman_occupied
        is_cman_occupied = False
        game.declare_winner(Player.SPIRIT)
        handle_end_game()
    elif clients[addr]['player'] == Player.SPIRIT:
        global is_spirit_occupied
        is_spirit_occupied = False
        game.declare_winner(Player.CMAN)
        handle_end_game()
    clients.pop(addr)

def handle_end_game():
    winner = game.get_winner()
    start_time = time.time()
    while time.time() - start_time < 10:
        send_win_message(winner)
        time.sleep(1)
    game.restart_game()
    clients.clear()

def send_win_message(winner):
    winner_in_bytes = b'\x01' if winner == Player.CMAN else b'\x02'
    spirit_score = bytes(3 - game.get_game_progress()[0])
    cman_score = bytes(game.get_game_progress()[1])
    for client_addr in clients.keys():
        try:
            message = b'\x8F' + winner_in_bytes + spirit_score
            server_socket.sendto(message, client_addr)
            print(f"Sending message to {client_addr}: {message}")
        except BlockingIOError:
            print(f"Failed to send win message to {client_addr}: socket buffer is full")

def publish_error(addr, message):
    try:
        message = b'\xFF' + message.encode()
        server_socket.sendto(message, addr)
        print(f"Sending error message to {addr}: {message}")
    except BlockingIOError:
        print(f"Failed to send error message to {addr}: socket buffer is full")

if __name__ == "__main__":
    main()
