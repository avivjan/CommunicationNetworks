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
    game = Game("cman_map.txt")
    
    port = parse_command_line_args().port
    print(f"Server will start on port {port}")
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(('localhost', port))
    server_socket.setblocking(False)  # Non-blocking socket
    
    print("Server started")
    
    last_update_time = time.time()
    
    try:
        while True:
            check_for_inactive_clients()
            update_client_game_state_periodically()
            read_sockets, _, _ = select.select([server_socket], [], [], 0)
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
        
        
def check_for_inactive_clients():
    current_time = time.time()
    for addr, client_data in list(clients.items()):
        if current_time - client_data['last_active'] > 10:  # 10-second timeout
            print(f"Client {addr} timed out.")
            handle_quit("", addr)
            
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
    parser = argparse.ArgumentParser(description="Start the cman_server with an optional port parameter.")
    parser.add_argument(
        '-p', 
        type=int, 
        default=1337, 
        help='Specify the port number. Default is 1337.'
    )
    args = parser.parse_args()
    return args

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
        publish_error(addr, "Game has already started")
        return
    
    if role == '\x01':
        if is_cman_occupied:
            publish_error(addr, "Cman is already occupied")
            return
        clients[addr] = {'player': Player.CMAN, 'last_active': time.time()}
        is_cman_occupied = True
        publish_game_state_update_to_all()
    elif role == '\x02':
        if is_spirit_occupied:
            publish_error(addr, "Spirit is already occupied")
            return
        clients[addr] = {'player': Player.SPIRIT, 'last_active': time.time()}
        is_spirit_occupied = True
        publish_game_state_update_to_all()
    else:
        publish_error(addr, "Invalid role in join message")
        return


def calculate_collected_points():
    collected_points = ""
    points = game.get_points()
    for point in points.values():
        collected_points += str(point)
    collected_points = collected_points.encode()
    return collected_points

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
    
    game.apply_move(clients[addr]['player'], direction)
    if game.get_winner() != Player.NONE:
        handle_end_game(game.get_winner())
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
        freeze = b'\x00' if player == Player.NONE else bytes(game.can_move(player))
        try:
            server_socket.sendto(opcode + freeze + cman_cor + spirit_cor + spirit_score + collected_points, client_addr)
        except BlockingIOError:
            print(f"Failed to send game state update to {client_addr}: socket buffer is full")


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
        declare_winner(Player.SPIRIT)
        handle_end_game(Player.SPIRIT)
    elif clients[addr]['player'] == Player.SPIRIT:
        global is_spirit_occupied
        is_spirit_occupied = False
        declare_winner(Player.CMAN)
        handle_end_game(Player.CMAN)
    del clients[addr]

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
            server_socket.sendto(b'\x8F' + winner_in_bytes + spirit_score, client_addr)
        except BlockingIOError:
            print(f"Failed to send win message to {client_addr}: socket buffer is full")

def publish_error(addr, message):
    try:
        server_socket.sendto(b'\xFF' + message.encode(), addr)
    except BlockingIOError:
        print(f"Failed to send error message to {addr}: socket buffer is full")

if __name__ == "__main__":
    main()
