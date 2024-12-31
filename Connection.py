class Connection:
    def __init__(self, socket):
        self.socket = socket
        self.read_buffer = ''
        self.status = 'greeting'
        self.username = None