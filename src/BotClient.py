import socket
import random
from Client import Client


class BotClient(Client):
    def __init__(self):
        super().__init__()
        self.possible_team_names = ["Bot Luffy", "Bot Zoro", "Bot Nami", "Bot Ussopp", "Bot Brook", "Bot Sanji",
                                    "Bot Robin", "Bot Chopper", "Bot Jimbei", "Bot Franky", "Bot Buggy", "Bot Shanks",
                                    "Bot mihawk", "Bot Hancock", "Bot Crocodile", "Bot Garp", "Bot Trafalgar Law", "Bot Vivi"
                                    , "Bot Bellamy", "Bot Wapol", "Bot Pica", "Bot Doflamingo", "Bot Ace", "Bot Sabo",
                                    "Bot Dragon", "Bot Roger"]
        self.TEAM_NAME = random.choice(self.possible_team_names)

        # print("bot client created")
        print("Bot Client started, listening for offer requests...")

    # def start(self):
    #     self.listen_for_offer()

    def receive_messages(self):
        """
            Receives and handles messages from the server.
            acting as a bot, the bot will answer the server's questions with a random choice of True or False.
        """
        while True:
            try:
                message = self.tcp_socket.recv(1024).decode().rstrip('\n')
                self.tcp_socket.settimeout(22)  # Reset timeout to 22 seconds after each successful message reception
                if message:
                    if message.endswith("question"):
                        # print without the word 'question'
                        print(message[:len(message) - len("question")])
                        random_choice = random.choice(["T", "F"])
                        self.tcp_socket.sendall(random_choice.encode())
                    elif message.endswith("exit"):
                        # print without the word 'exit'
                        print(message[:len(message) - len("exit")])
                        print("Game ended! listening for a new offer requests...")
                        break
                    else:
                        print(message)

            except socket.timeout:
                print("Timeout: No message received from the server for 22 seconds, disconnecting the connection to the"
                      " server and listening for a new offer requests...")
                DISCONNECT_MESSAGE = "disconnect"
                self.tcp_socket.sendall(DISCONNECT_MESSAGE.encode())
                break
            except socket.error:
                print("Server disconnected, listening for offer requests...")
                break
