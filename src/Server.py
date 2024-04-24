import socket
import struct
import subprocess
import time
import threading
import random
import json
import requests


def get_wifi_ip():
    try:
        output = subprocess.check_output(["ifconfig", "en0"]).decode("utf-8")
        lines = output.split("\n")
        for line in lines:
            if "inet " in line:
                return line.split()[1]  # Extract the IP address from the line
    except Exception as e:
        print("Error:", e)


class Server:

    def __init__(self):
        self.questions = {}
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.MAGIC_COOKIE = 0xabcddcba
        self.game_lost = False
        self.SERVER_PORT = 13117
        self.MESSAGE_TYPE = 0x2
        self.conn_made = -1
        self.TEAM_NAME = "Mystic"
        self.SERVER_NAME = "EchoNexus".ljust(32, ' ')
        self.UDP_BROADCAST_ADDRESS = "<broadcast>"
        self.player_online_count = 0
        self.client_list = {}
        self.flag = False
        self.socket_server = None  # Initialize socket_server as None
        # get local ip address
        # for Yuval
        self.host = get_wifi_ip()
        # for other
        # self.host = socket.gethostbyname(socket.gethostname())

        self.SERVER_TCP_PORT = self.find_available_port()

        self.true_statements = {'Y', 'T', 'y', 't', '1'}
        self.false_statements = {'N', 'F', 'n', 'f', '0'}
        print("Server started, listening on IP address %s" % self.host)
        self.currentQuestion = None
        self.main()  # Start the server

    def resetQuestionsForTrivia(self):
        API_URL = "https://opentdb.com/api.php?amount=20&difficulty=easy&type=boolean"
        response = requests.get(API_URL)
        data = json.loads(response.text)
        questions = data["results"]
        for question in questions:
            question["question"] = "True or False: " + question["question"]
            self.questions[question["question"]] = question["correct_answer"]

    def find_available_port(self):
        """
        Find an available port for the server to bind to.
        :return: port number
        """
        server_tcp_port_range = range(1024, 65535)
        for port in server_tcp_port_range:
            try:
                server_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server_tcp_socket.bind((self.host, port))
                # Close the socket if bind succeeds
                server_tcp_socket.close()
                return port
            except OSError:
                # Port is already in use, try the next one
                pass

    # Start broadcasting offers in a separate thread
    def broadcast_offers(self):
        """
        Broadcast offer packets to all clients on the network, inviting them to connect to the server,
        while also listening for incoming connections from clients. The server will start a new game if 2 players are
        connected And 10 seconds after the last player joined, the server will start a new game.
        """
        # Reset the questions for current round
        self.resetQuestionsForTrivia()
        print("Server UDP socket binded to %s" % self.SERVER_PORT)

        # Create a socket object using UDP
        socket_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        socket_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        socket_server.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        # Build the offer packet
        packet = struct.pack('!IB32sH', self.MAGIC_COOKIE, self.MESSAGE_TYPE,
                             self.SERVER_NAME.encode('utf-16-le'), self.SERVER_TCP_PORT)
        # Bind the socket to the specified IP address
        socket_server.bind((self.host, self.SERVER_PORT))
        while self.conn_made != 0:
            try:

                # Send the offer packet
                socket_server.sendto(packet, (self.UDP_BROADCAST_ADDRESS, self.SERVER_PORT))
                print("Invitation packet broadcast")
                time.sleep(1)
                self.conn_made -= 1

            except (socket.timeout, socket.error) as e:
                print(f"Error broadcasting: {e}")
                self.client_list.clear()

        # Start a new game
        self.start_game()
        # When the game ends, close the previous connection and start again broadcast_offers
        socket_server.close()
        self.broadcast_offers()

    def serverTCP(self):
        """
        Start the TCP server and listen for incoming connections from clients
        """
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self.tcp_socket.bind((self.host, self.SERVER_TCP_PORT))
        self.tcp_socket.listen()

        while True:
            print("Server TCP socket listening...")
            client_conn, client_addr = self.tcp_socket.accept()
            print(f"Connected by {client_addr}")
            client_thread = threading.Thread(target=self.handle_client, args=(client_conn, client_addr))
            client_thread.start()

    def handle_client(self, conn, addr):
        """
        Handle a new client connection and add it to the client_list
        :param conn: client connection socket
        :param addr: IP address of the client
        """
        flag = True
        while flag:
            try:
                number_of_clients = 0
                team_name = conn.recv(1024).decode().strip('\n')
                for address, client_info in self.client_list.items():
                    number_of_clients += 1
                    if client_info['team_name'] == team_name:
                        team_name = team_name + " (2)"
                        conn.sendall(team_name.encode())
                        flag = False
                        break
                if number_of_clients == len(self.client_list.keys()) and flag:
                    msg1 = "You have connected successfully"
                    conn.sendall(msg1.encode())
                    break

            except Exception:
                pass
        self.client_list[addr] = {'connection': conn, 'team_name': team_name, 'inGame': False}
        print(f"Client connected: {team_name}")

        if len(self.client_list) > 1 and not team_name.startswith("Bot"):
            # Start a timer
            self.conn_made = 10

    def start_game(self):
        """
        Start the trivia game by sending the welcome message to all clients
        and asking the questions from the questions dictionary until the game ends.
        :return:
        """
        # keys_list = list(self.barcelona_questions.keys())
        self.game_lost = False
        round = 1
        # Start the game loop
        while not self.game_lost and round < len(self.questions):
            # case for the first question to Clients
            if round == 1:
                self.currentQuestion = self.askRandomQuestion()
                # Construct the welcome message
                welcome_message = (
                    f"Welcome to the {self.TEAM_NAME} server, where we are answering trivia questions about "
                    f"any category.\n")

                # Add player names to the welcome message
                for i, (addr, client_info) in enumerate(self.client_list.items(), start=1):
                    welcome_message += f"Player {i}: {client_info['team_name']}\n"

                for addr, client_info in self.client_list.items():
                    try:
                        client_info['connection'].sendall(welcome_message.encode())
                        client_info['inGame'] = True
                    except socket.error:
                        client_info['inGame'] = False
                        # self.client_list.pop(addr)
                # Add the first trivia question to the welcome message
                time.sleep(5)
                welcome_message += "==\n"
                welcome_message = self.currentQuestion
                # welcome_message += keys_list[0]
                welcome_message += "question"

                # Send the welcome message to all clients
                for addr, client_info in self.client_list.items():
                    try:
                        client_info['connection'].sendall(welcome_message.encode())
                    except socket.error:
                        client_info['inGame'] = False
                        # self.client_list.pop(addr)


            # add to responses list a tuple that the first value is the team name that answer the current question and
            # the second value is true if the answer is correct or false either
            responses = []
            for addr, client_info in self.client_list.items():
                try:
                    if not client_info['inGame']:
                        continue
                    client_info['connection'].settimeout(10)
                    response = client_info['connection'].recv(1024).decode().strip()
                    # print("Received response from client:", response)
                    is_correct = (response in self.true_statements and self.questions[self.currentQuestion] == "True"
                                  or response in self.false_statements and self.questions[self.currentQuestion] == "False")
                    responses.append((client_info['team_name'], is_correct))
                except ConnectionResetError:
                    client_info['inGame'] = False
                    # self.client_list.pop(addr)
                except socket.timeout:
                    print(f"{client_info['team_name']} did not answer in time, so the answer is incorrect")
                    responses.append((client_info['team_name'], False))

            self.questions.pop(self.currentQuestion)

            # Generate messages for all the Clients based on their responses
            message = ""
            for team_name, is_correct in responses:
                message += f"{team_name} is {'correct!' if is_correct else 'incorrect!'}\n"
                # Send the message to all players
            message += "responses"
            for addr, player_info in self.client_list.items():
                if player_info['inGame']:
                    try:
                        player_info['connection'].sendall(message.encode())
                    except socket.error:
                        player_info['inGame'] = False
                        # self.client_list.pop(addr)
            time.sleep(6)

            # Check_answers return true if one team stayed and the game ends
            if self.check_answers(responses, round):
                # End the game
                end_message = "Game over, sending out offer requests...\n"
                print(end_message)

                # Close TCP connections
                for addr, player_info in self.client_list.items():
                    player_info['connection'].close()
                self.client_list = {}
                # Reset the game state
                self.game_lost = True
            else:
                round += 1
        # Restart broadcasting offers
        self.conn_made = -1
        self.game_lost = False

    # return True if the game end or False either
    def check_answers(self, responses, round):
        """
        Check the responses of the players and determine if the game should continue to the next round
        :param responses: array of tuples containing the team name and a boolean value indicating if the answer is correct
        :param round: round number
        :return: true if the game should end, false otherwise
        """
        # Get the names of the players who answered correctly
        correct_players = [team_name for team_name, is_correct in responses if is_correct]
        wrong_players = [team_name for team_name, is_correct in responses if not is_correct]
        # If all responses are incorrect, continue to next round
        if len(correct_players) == 0:
            messageForNextRound = "No correct answers for this round, all of you continue to the next round"
            self.generateNextQuestion(messageForNextRound, round)
            return False

        if len(wrong_players) > 0:
            for team_name in wrong_players:
                win_message = "Game over!" + "\n"
                win_message += f"You lost this time: {team_name} !"
                win_message += "exit"
                for addr, player_info in self.client_list.items():
                    if player_info['team_name'] == team_name:
                        try:
                            player_info['connection'].sendall(win_message.encode())
                            player_info['inGame'] = False
                        except socket.error:
                            player_info['inGame'] = False
                            # self.client_list.pop(addr)

        # Only one team answered correct
        if len(correct_players) == 1:
            # Get the name of the winning player
            winner_name = correct_players[0]
            # Send message announcing the winner to all players
            win_message = "Game over!" + "\n"
            win_message += f"Congratulations to the winner: {winner_name} "
            win_message += "exit"
            for addr, player_info in self.client_list.items():
                try:
                    player_info['connection'].sendall(win_message.encode())
                except socket.error:
                    player_info['inGame'] = False
                    # self.client_list.pop(addr)

            # End the game
            self.game_lost = True
            return True

        # More than one team answered correct
        else:
            self.generateNextQuestion("", round)
            return False

    def generateNextQuestion(self,messageForNextRound, round):
        """
        Generate the next trivia question and send it to all players
        :param messageForNextRound: generated message for the next round
        :param round: round number
        """
        messageForNextRound += f"\nRound {round + 1}, played by"
        for addr, client_info in self.client_list.items():
            if client_info['inGame']:
                messageForNextRound += f" {client_info['team_name']} and"
        messageForNextRound = messageForNextRound[:-4]  # Remove the last 'and'
        messageForNextRound += ":\n"
        messageForNextRound += "==\n"
        # Add the next trivia question to the message
        # keys_list = list(self.barcelona_questions.keys())
        self.currentQuestion = self.askRandomQuestion()
        messageForNextRound += f"{self.currentQuestion}\n"
        messageForNextRound += "question"

        # Send the  message to all clients
        for addr, client_info in self.client_list.items():
            if client_info['inGame']:
                try:
                    client_info['connection'].sendall(messageForNextRound.encode())
                except socket.error:
                    client_info['inGame'] = False
                    # self.client_list.pop(addr)

    # Generate random question and return it
    def askRandomQuestion(self):
        # Check if the dictionary is not empty
        if self.questions:
            randomQuestion = random.choice(list(self.questions.keys()))
            return randomQuestion
        else:
            print("No more questions available!")

    def main(self):
        """
        start the server, start the TCP server and broadcast offers.
        :return:
        """
        # game_state = "Waiting for clients"
        # last_client_joined_time = time.time()

        tcp_thread = threading.Thread(target=self.serverTCP)
        tcp_thread.start()

        udp_thread = threading.Thread(target=self.broadcast_offers)
        udp_thread.start()
        # Start the TCP server thread


        udp_thread.join()
        tcp_thread.join()

    # def update_players_state(self, names_list):
    #     for addr, client_info in self.client_list.items: