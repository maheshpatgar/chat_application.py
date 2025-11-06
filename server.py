import socket
import threading
import sys
import traceback

HOST = '127.0.0.1'
PORT = 6666
LISTENER_LIMIT = 5

# active_clients: list of dicts { "username": str, "sock": socket.socket }
active_clients = []
clients_lock = threading.Lock()

def send_message_to_client(sock, message):
    """Send a UTF-8 message to a single client. If sending fails, return False."""
    try:
        sock.sendall(message.encode('utf-8'))
        return True
    except Exception:
        try:
            sock.close()
        except Exception:
            pass
        return False

def send_messages_to_all(message):
    """
    Broadcast a message to all connected clients.
    Removes clients that can't be reached.
    """
    to_remove = []
    with clients_lock:
        for entry in list(active_clients):
            sock = entry["sock"]
            ok = send_message_to_client(sock, message)
            if not ok:
                to_remove.append(entry)

        for entry in to_remove:
            try:
                active_clients.remove(entry)
            except ValueError:
                pass
            print(f"[SERVER] Removed unreachable client: {entry['username']}")
    # Optionally log the broadcast on server console
    print(f"[BROADCAST] {message}")

def listen_for_messages(client_sock, username):
    """Thread: receive messages from one client and broadcast them."""
    try:
        while True:
            try:
                data = client_sock.recv(2048)
            except OSError:
                # socket closed
                break

            if not data:
                # client disconnected gracefully
                break

            try:
                message = data.decode('utf-8')
            except Exception:
                message = repr(data)

            final_msg = f"{username}~{message}"
            print(f"{username}: {message}")
            send_messages_to_all(final_msg)
    except Exception:
        print(f"[ERROR] Exception in listener for {username}:")
        traceback.print_exc()
    finally:
        remove_client(client_sock, username)

def remove_client(client_sock, username):
    """Remove client from list, close socket, and notify others."""
    with clients_lock:
        found = None
        for entry in active_clients:
            if entry["sock"] == client_sock:
                found = entry
                break
        if found:
            try:
                active_clients.remove(found)
            except ValueError:
                pass

    try:
        client_sock.close()
    except Exception:
        pass

    print(f"Client '{username}' disconnected")
    # Announce to everyone except the removed client
    send_messages_to_all(f"SERVER~{username} has left the chat")

def client_handler(client_sock, addr):
    """
    Accept first message as username and then spin off a listener thread.
    If username is empty or missing, close connection.
    """
    try:
        client_sock.settimeout(10.0)  # initial timeout while waiting for username
        raw = client_sock.recv(2048)
        client_sock.settimeout(None)  # remove timeout
        if not raw:
            print(f"Connection from {addr} closed before sending username.")
            client_sock.close()
            return

        username = raw.decode('utf-8').strip()
        if username == "":
            print(f"Client at {addr} sent an empty username. Closing.")
            client_sock.close()
            return

        with clients_lock:
            active_clients.append({"username": username, "sock": client_sock})

        print(f"'{username}' connected from {addr[0]}:{addr[1]}")
        send_messages_to_all(f"SERVER~{username} joined the chat")

        # Start listener thread for that client
        listener = threading.Thread(target=listen_for_messages, args=(client_sock, username), daemon=True)
        listener.start()

    except Exception:
        print(f"[ERROR] Error receiving username from {addr}:")
        traceback.print_exc()
        try:
            client_sock.close()
        except Exception:
            pass

def server_send_messages():
    """Allow server operator to broadcast messages by typing in console."""
    try:
        while True:
            msg = input()
            if msg is None:
                break
            txt = msg.strip()
            if txt:
                send_messages_to_all(f"SERVER~{txt}")
    except EOFError:
        # stdin closed
        pass
    except Exception:
        print("[ERROR] Exception in server_send_messages:")
        traceback.print_exc()

def main():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_sock.bind((HOST, PORT))
    except Exception as e:
        print(f"Unable to bind to {HOST}:{PORT} -> {e}")
        return

    server_sock.listen(LISTENER_LIMIT)
    print(f"Server running and listening on {HOST}:{PORT}")

    # Thread to allow server operator to type broadcasts
    threading.Thread(target=server_send_messages, daemon=True).start()

    try:
        while True:
            try:
                client_sock, address = server_sock.accept()
            except OSError:
                # socket closed
                break

            print(f"Connected to client {address[0]}:{address[1]}")
            # start handler thread
            threading.Thread(target=client_handler, args=(client_sock, address), daemon=True).start()

    except KeyboardInterrupt:
        print("\n[SERVER] Shutdown requested (KeyboardInterrupt). Closing server...")
    except Exception:
        print("[ERROR] Unexpected server error:")
        traceback.print_exc()
    finally:
        # Close all client sockets
        with clients_lock:
            for entry in active_clients:
                try:
                    entry["sock"].close()
                except Exception:
                    pass
            active_clients.clear()

        try:
            server_sock.close()
        except Exception:
            pass
        print("[SERVER] Clean shutdown complete.")
        sys.exit(0)

if __name__ == "__main__":
    main()

