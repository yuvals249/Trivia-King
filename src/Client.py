import socket
import struct
import subprocess
from abc import ABC, abstractmethod


def get_wifi_ip():
    try:
        output = subprocess.check_output(["ifconfig", "en0"]).decode("utf-8")
        lines = output.split("\n")
        for line in lines:
            if "inet " in line:
                return line.split()[1]  # Extract the IP address from the line
    except Exception as e:
        print("Error:", e)


class Client(ABC):
    def __init__(self):
        self.UDP_PORT = 13117
        self.SERVER_NAME_LENGTH = 32
        self.SERVER_ADDRESS = None
        self.SERVER_PORT = None
        self.player_name = None
        self.TEAM_NAME = None

        # get local ip address
        # for Yuval
        self.host = get_wifi_ip()
        # for other
        # self.host = socket.gethostbyname(socket.gethostname())

        self.tcp_socket = None

    def start(self):
        self.listen_for_offer()

    def listen_for_offer(self):
        """
            Listens for offer messages from the server.
            Once an offer message is received, the client will connect to the server.
        :return:
        """
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)  # Allow reusing the address
        udp_socket.bind(('0.0.0.0', self.UDP_PORT))

        while True:
            data, addr = udp_socket.recvfrom(1024)
            magic_cookie, message_type, server_name, server_port = struct.unpack('!IB32sH', data)
            if magic_cookie == 0xabcddcba and message_type == 0x2:
                server_name = server_name.decode('utf-16-le').rstrip('\x00').rstrip()
                self.SERVER_ADDRESS = addr[0]
                self.SERVER_PORT = server_port
                print(
                    f"Received offer from server {server_name} at address {self.SERVER_ADDRESS}, attempting to connect...")
                self.connect_to_server()
                break
        udp_socket.close()
        self.listen_for_offer()

    def connect_to_server(self):
        """
            Connects to the server over TCP.
            Sends the team name to the server.
            Receives messages from the server if the connection is successful.
        """
        try:
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            self.tcp_socket.connect((self.SERVER_ADDRESS, self.SERVER_PORT))
            print("Connected to the server over TCP")
            # Send team name to the server
            while True:
                self.tcp_socket.sendall(f"{self.TEAM_NAME}\n".encode())
                msg = self.tcp_socket.recv(1024).decode().strip('\n')
                if msg:
                    if msg.endswith("successfully"):
                        break
                    else:
                        self.TEAM_NAME = msg
                        break

            self.receive_messages()

            self.tcp_socket.close()

        except ConnectionRefusedError:
            print("Connection refused: The server is not accepting connections on the specified port")
        except TimeoutError:
            print("Connection attempt timed out")
        except Exception as e:
            print("An error occurred:", e)



    @abstractmethod
    def receive_messages(self):
        pass

    # def wait_for_game(self):
    #     pass