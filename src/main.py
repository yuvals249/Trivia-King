from Server import *
from BotClient import BotClient
from HumanClient import HumanClient


def start_server1():
    Server()


def start_server2():
    Server()

def start_humanClients():
    humanClient1 = HumanClient()
    humanClient1.start()



def start_botClients():
    botClient1 = BotClient()
    botClient1.start()
    # botClient2 = BotClient()
    # botClient2.start()
    # botClient3 = BotClient()
    # botClient3.start()
    # botClient4 = BotClient()
    # botClient4.start()
    # botClient5 = BotClient()
    # botClient5.start()


if __name__ == "__main__":
    # Wait for a short time to ensure the server starts before clients
    server_thread = threading.Thread(target=start_server1)
    server_thread.start()
    # time.sleep(5)
    # server_thread1 = threading.Thread(target=start_server2)
    # server_thread1.start()

    botClient_thread = threading.Thread(target=start_botClients)
    botClient_thread.start()

    # botClient_thread2 = threading.Thread(target=start_botClients)
    # botClient_thread2.start()
    # botClient_thread3 = threading.Thread(target=start_botClients)
    # botClient_thread3.start()
    # botClient_thread4 = threading.Thread(target=start_botClients)
    # botClient_thread4.start()

    # humanClient_thread = threading.Thread(target=start_humanClients)
    # humanClient_thread.start()

    start_humanClients()

    try:
        server_thread.join()
        botClient_thread.join()
        # humanClient_thread.join()
    except KeyboardInterrupt:
        print("The program stopped")
