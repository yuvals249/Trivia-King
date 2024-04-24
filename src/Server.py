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
        self.all_bots = True
        self.flag = False
        self.socket_server = None  # Initialize socket_server as None
        # get local ip address
        self.host = get_wifi_ip()
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

        if not team_name.startswith("Bot"):
            self.all_bots = False

        if len(self.client_list) > 1 and not self.all_bots:
            # Start a timer
            self.conn_made = 10

    def start_game(self):
        """
        Start the trivia game by sending the welcome message to all clients
        and asking the questions from the questions dictionary until the game ends.
        :return:
        """
        self.game_lost = False
        round_number = 1

        # Start the game loop
        while not self.game_lost and round_number < len(self.questions):

            # case for the first question to Clients
            if round_number == 1:
                self.send_welcome_message()

                time.sleep(5)

                self.currentQuestion = self.askRandomQuestion()
                self.send_question_to_clients()

            responses = self.collect_responses()
            self.questions.pop(self.currentQuestion)
            self.process_responses(responses, round_number)

            if self.game_lost:
                # End the game
                end_message = "Game over, sending out offer requests...\n"
                print(end_message)
                self.reset_game_state()

                # Restart broadcasting offers
                break
            else:
                round_number += 1

    def send_welcome_message(self):
        """
        Send a welcome message to all clients.
        """
        welcome_message = f"Welcome to the {self.TEAM_NAME} server, where we are answering trivia questions about " \
                          f"any category.\n"

        # Add player names to the welcome message
        for i, (addr, client_info) in enumerate(self.client_list.items(), start=1):
            welcome_message += f"Player {i}: {client_info['team_name']}\n"

        for addr, client_info in self.client_list.items():
            try:
                client_info['connection'].sendall(welcome_message.encode())
                client_info['inGame'] = True
            except socket.error:
                client_info['inGame'] = False

    def send_question_to_clients(self):
        """
        Send the trivia question to all clients.
        """
        question_message = f"{self.currentQuestion} question"
        for addr, client_info in self.client_list.items():
            if client_info['inGame']:
                try:
                    client_info['connection'].sendall(question_message.encode())
                except socket.error:
                    client_info['inGame'] = False

    def collect_responses(self):
        """
        Collect responses from all clients.
        """
        responses = []
        for addr, client_info in self.client_list.items():
            try:
                if not client_info['inGame']:
                    continue
                client_info['connection'].settimeout(10)
                response = client_info['connection'].recv(1024).decode().strip()
                is_correct = (response in self.true_statements and self.questions[self.currentQuestion] == "True"
                              or response in self.false_statements and self.questions[self.currentQuestion] == "False")
                responses.append((client_info['team_name'], is_correct))
            except ConnectionResetError:
                client_info['inGame'] = False
            except socket.timeout:
                responses.append((client_info['team_name'], False))
                print(f"{client_info['team_name']} did not answer in time, so the answer is incorrect")
        return responses

    def process_responses(self, responses, round_number):
        """
        Process responses from clients and determine game outcome.
        """
        self.update_participants_on_results(responses)

        time.sleep(6)

        # Get the names of the players who answered correctly
        correct_players = [team_name for team_name, is_correct in responses if is_correct]
        wrong_players = [team_name for team_name, is_correct in responses if not is_correct]

        # If all responses are incorrect, continue to next round
        if len(correct_players) == 0:
            messageForNextRound = "No correct answers for this round, all of you continue to the next round"
            self.generateNextQuestion(messageForNextRound, round_number)
            return

        if len(wrong_players) > 0:
            self.handle_wrong_answers(wrong_players)

        if len(correct_players) == 1:
            self.handle_single_winner(correct_players)

        # More than one team answered correct
        else:
            self.generateNextQuestion("", round_number)

    def update_participants_on_results(self, responses):
        # Generate messages for all the Clients based on their responses
        message = ""
        for team_name, is_correct in responses:
            message += f"{team_name} is {'correct!' if is_correct else 'incorrect!'}\n"
        message += "responses"

        # Send the message to all players
        for addr, player_info in self.client_list.items():
            if player_info['inGame']:
                try:
                    player_info['connection'].sendall(message.encode())
                except socket.error:
                    player_info['inGame'] = False

    def handle_wrong_answers(self, wrong_players):
        """
        Handle responses where the answer is incorrect.
        """
        for team_name in wrong_players:
            win_message = "Game over!\n"
            win_message += f"You lost this time: {team_name} ! exit"
            for addr, player_info in self.client_list.items():
                if player_info['team_name'] == team_name:
                    try:
                        player_info['connection'].sendall(win_message.encode())
                        player_info['inGame'] = False
                    except socket.error:
                        player_info['inGame'] = False

    def handle_single_winner(self, correct_players):
        """
        Handle responses where only one team answered correctly.
        """
        # Get the name of the winning player
        winner_name = correct_players[0]
        # Send message announcing the winner to all players
        win_message = "Game over!\n"
        win_message += f"Congratulations to the winner: {winner_name} exit"
        for addr, player_info in self.client_list.items():
            try:
                player_info['connection'].sendall(win_message.encode())
            except socket.error:
                player_info['inGame'] = False

        # End the game
        self.game_lost = True

    def reset_game_state(self):
        """
        Reset the game state.
        """
        # Close TCP connections
        for addr, player_info in self.client_list.items():
            player_info['connection'].close()

        self.client_list = {}
        self.conn_made = -1
        self.game_lost = False

    def generateNextQuestion(self,messageForNextRound, round_number):
        """
        Generate the next trivia question and send it to all players
        :param messageForNextRound: generated message for the next round
        :param round: round number
        """
        messageForNextRound += f"\nRound {round_number + 1}, played by"
        for addr, client_info in self.client_list.items():
            if client_info['inGame']:
                messageForNextRound += f" {client_info['team_name']} and"
        messageForNextRound = messageForNextRound[:-4]  # Remove the last 'and'
        messageForNextRound += ":\n"
        messageForNextRound += "==\n"
        # Add the next trivia question to the message
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

        # Start the TCP server thread
        tcp_thread = threading.Thread(target=self.serverTCP)
        tcp_thread.start()

        # Start the UDP server thread
        udp_thread = threading.Thread(target=self.broadcast_offers)
        udp_thread.start()

        udp_thread.join()
        tcp_thread.join()
