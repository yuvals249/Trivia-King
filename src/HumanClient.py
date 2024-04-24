import math
import socket
import threading
import time
import tkinter as tk
from tkinter.font import Font

from Client import Client


class HumanClient(Client):
    def __init__(self):
        super().__init__()
        self.first_msg = False
        self.TEAM_NAME = 'Hapoel Tel-Aviv'
        # print("human client created")
        print("Human Client started, listening for offer requests...")
        self.input_received = None
        self.message_label = None
        self.input_entry = None
        self.timeout_pass = False
        self.gui = self.create_gui()

    # def start(self):
    #     self.listen_for_offer()

    def create_gui(self):
        """
            Initializes and configures the GUI for the Trivia Game Client.
            Sets up message labels, input field, send button, timer, and waiting message label.
            Returns the root GUI window.
        """

        gui = tk.Tk()
        gui.title("Trivia Game Client")
        gui.geometry("600x400")
        self.message_label = tk.Label(gui, text="Searching For A Game Host", wraplength=380, justify="center", font=("Arial", 15), pady=50)
        self.message_label.pack()

        self.input_entry = tk.Entry(gui)
        self.input_entry.pack()

        self.send_button = tk.Button(gui, text="Send", command=self.send_input, )
        self.send_button.pack()

        self.time_table = tk.Label(gui, text="", wraplength=380, justify="center", font=("Arial", 30), fg="red",
                                   pady=20)
        self.time_table.pack()
        self.hide_widgets()

        self.waiting_message_label = tk.Label(gui, text="", wraplength=380, justify="center", font=("Arial", 20),
                                              fg="DodgerBlue4"
                                              , pady=150)
        self.waiting_message_label.pack()

        return gui

    def receive_messages(self):
        """
            Receives and handles messages from the server.
            Updates the GUI with incoming messages and game status.
            """
        self.hide_widgets()
        self.first_msg = True
        temp_labels = []
        self.message_label.config(text="")
        thread = threading.Thread(target=self.wait_for_game)
        thread.start()
        while True:
            try:
                message = self.tcp_socket.recv(1024).decode().rstrip('\n')
                self.tcp_socket.settimeout(22)  # Reset timeout to 22 seconds after each successful message reception
                for label in temp_labels:
                    label.pack_forget()
                if message:

                    # in case of question has been asked
                    if message.endswith("question"):

                        # print without the word 'question'
                        self.timeout_pass = False
                        self.show_widgets()
                        self.message_label.config(text=message[:len(message) - len("question")], font=("Ariel", 12),
                                                  fg="black")
                        self.timeout_thread()
                        print(message[:len(message) - len("question")])

                    # in case the user needs lost and needs to disconnect
                    elif message.endswith("exit"):

                        # print without the word 'exit'
                        print(message[:len(message) - len("exit")])
                        print("Game ended! listening for a new offer requests...")
                        self.message_label.config(text=message[:len(message) - len("exit")],
                                                  fg="DodgerBlue4", font=("Roboto", 20)),

                        time.sleep(3)
                        break


                    # when the first msg arrives of the welcome

                    elif message.startswith("Welcome"):
                        self.message_label.config(text=message, fg="DodgerBlue4", font=("Roboto", 19))
                        self.first_msg = False

                    # the responses of all clients in the game

                    elif message.endswith("responses"):

                        message = message[:len(message) - len(" responses")]
                        sentences = message.split("\n")
                        print(len(sentences))
                        for sentence in sentences:
                            if sentence.endswith("incorrect!"):
                                color = "red"
                                emoji = "😞"
                            else:
                                color = "green"
                                emoji = "😊"

                            custom_font = Font(family="Segoe UI Emoji", size=12)
                            label = tk.Label(self.gui, text=f"{sentence} {emoji} ", font=custom_font, fg=color)
                            label.pack()
                            temp_labels.append(label)
                            self.message_label.config(text="")

                    # other msgs possible.
                    else:
                        self.message_label.config(text=message)
                        time.sleep(1)
                        print(message[:len(message) - 1])


            except socket.timeout:
                print("Timeout: No message received from the server for 22 seconds, disconnecting the connection to the"
                      " server and listening for a new offer requests...")
                DISCONNECT_MESSAGE = "disconnect"
                self.tcp_socket.sendall(DISCONNECT_MESSAGE.encode())

                break
            except socket.error:
                print("Server disconnected, listening for a new offer requests...")
                self.message_label.config(text="Server disconnected, listening for a new offer requests...")
                break

    def timeout_thread(self):
        """
            Manages the countdown timer during gameplay, updating the GUI to display the remaining time for player response.
            If the timeout passes without input, certain GUI widgets are hidden to prompt for the next game action.
            """
        start_time = time.time()
        while time.time() - start_time < 10:
            # if self.input_received.is_set():
            #     return  # Exit the thread if input was received
            if self.timeout_pass:
                self.time_table.config(text="")
                return

            time_left = 10 - (time.time() - start_time)
            self.time_table.config(text=f"{math.ceil(time_left)}")
            time.sleep(1)
        # if not self.input_received.is_set():  # Check if input was received after the loop
        #     pyautogui.press('enter')  # Simulate pressing the Enter key to trigger timeout
        self.hide_widgets()

    def send_keyboard_input(self):
        self.input_received = threading.Event()
        thread = threading.Thread(target=self.timeout_thread)
        thread.start()
        try:
            user_input = input("Enter your input: \n")
            self.input_received.set()  # Mark input as received
            self.tcp_socket.sendall(user_input.encode())
        except (KeyboardInterrupt, EOFError, UnicodeDecodeError):
            print("Server disconnected, listening for offer requests...2")
        finally:
            thread.join()  # Wait for the timeout thread to finish

    def send_input(self):
        """
            Sends user input to the server during gameplay.

            This method retrieves user input from the GUI input field and sends it to the server.
            If no input is provided, a default value 'x' is sent.
            It hides certain GUI widgets after sending the input and clears the input field.
        """
        self.timeout_pass = True
        try:
            user_input = self.input_entry.get()
            if user_input == "":
                user_input = "x"
            # self.input_received.set()
            self.hide_widgets()
            self.tcp_socket.sendall(user_input.encode())
            self.input_entry.delete(0, tk.END)  # Clear input
        except (KeyboardInterrupt, EOFError, UnicodeDecodeError, ConnectionResetError):
            print("Server disconnected, listening for offer requests...2")


    def start(self):
        network_thread = threading.Thread(target=super().start)  # Use inheritance
        network_thread.start()
        self.gui.mainloop()  # Start GUI event loop

    def hide_widgets(self):
        self.input_entry.pack_forget()
        self.send_button.pack_forget()
        self.time_table.pack_forget()

    def show_widgets(self):
        self.input_entry.pack()
        self.send_button.pack()
        self.time_table.pack()

    def wait_for_game(self):
        """
            Displays a waiting message while searching for a new game.
            Updates the message label with loading dots to indicate the search progress.
        """
        self.message_label.pack_forget()
        self.waiting_message_label.pack()
        temp = 0
        while self.first_msg:
            time.sleep(0.5)
            if temp == 0:
                self.waiting_message_label.config(text="Finding A New Game.")
            elif temp == 1:
                self.waiting_message_label.config(text="Finding A New Game. .")
            elif temp == 2:
                self.waiting_message_label.config(text="Finding A New Game. . .")
            else:
                self.waiting_message_label.config(text="Finding A New Game. . . .")
                temp = 0
                continue
            temp += 1
        self.waiting_message_label.pack_forget()
        self.message_label.pack()
