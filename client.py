import socket
import threading
import tkinter as tk
from tkinter import scrolledtext
from tkinter import messagebox

# Colors / fonts
DARK_GREY = '#121212'
MEDIUM_GREY = '#1F1B24'
OCEAN_BLUE = '#464EB8'
WHITE = 'white'
SMALL_FONT = ("Helvetica", 13)
FONT = ("Helvetica", 17)
BUTTON_FONT = ("Helvetica", 15)

HOST = '127.0.0.1'
PORT = 6666

# Global client socket variable (None until connected)
client = None
receiver_thread = None
connected = False

# ---------- Helper functions ----------
def add_message(message):
    """Add a line to the message box (thread-safe via `after`)."""
    def _append():
        message_box.config(state=tk.NORMAL)
        message_box.insert(tk.END, message + '\n')
        message_box.see(tk.END)
        message_box.config(state=tk.DISABLED)
    root.after(0, _append)


def listen_for_messages_from_server(sock):
    """Thread target: receive messages and display them."""
    global connected, client
    try:
        while True:
            try:
                data = sock.recv(4096)
            except OSError:
                # socket closed
                break

            if not data:
                # Server closed connection
                add_message("[SYSTEM] Server closed the connection.")
                break

            try:
                message = data.decode('utf-8')
            except Exception:
                # fallback
                message = repr(data)

            # If server uses "username~message" format, show accordingly
            if "~" in message:
                username, content = message.split("~", 1)
                add_message(f"[{username}] {content}")
            else:
                add_message(f"[SERVER] {message}")

    finally:
        # cleanup when thread ends
        connected = False
        client = None
        root.after(0, on_disconnected_ui_update)


# ---------- UI callbacks ----------
def connect():
    """Attempt to connect to server using username in the username_textbox."""
    global client, receiver_thread, connected

    if connected and client:
        messagebox.showinfo("Already connected", "You are already connected to the server.")
        return

    username = username_textbox.get().strip()
    if username == "":
        messagebox.showwarning("Missing username", "Please enter a username before joining.")
        return

    # Create socket and connect
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((HOST, PORT))
    except Exception as e:
        messagebox.showerror("Connection failed", f"Unable to connect to {HOST}:{PORT}\nError: {e}")
        return

    # send username as first message (server should expect this)
    try:
        s.sendall(username.encode('utf-8'))
    except Exception as e:
        s.close()
        messagebox.showerror("Send failed", f"Failed to send username to server.\nError: {e}")
        return

    client = s
    connected = True
    add_message(f"[SYSTEM] Connected to server as '{username}'")
    on_connected_ui_update()

    # start receiver thread
    receiver_thread = threading.Thread(target=listen_for_messages_from_server, args=(client,), daemon=True)
    receiver_thread.start()


def send_message():
    """Send the message currently in message_textbox to the server."""
    global client, connected
    if not connected or client is None:
        messagebox.showwarning("Not connected", "You are not connected to a server.")
        return

    message = message_textbox.get().strip()
    if message == "":
        # don't send empty messages
        return

    try:
        client.sendall(message.encode('utf-8'))
        # Optionally show sent messages locally (uncomment if desired)
        # add_message(f"[You] {message}")
        message_textbox.delete(0, tk.END)
    except Exception as e:
        add_message("[SYSTEM] Failed to send message. Server may be offline.")
        try:
            client.close()
        except Exception:
            pass
        client = None
        connected = False
        on_disconnected_ui_update()


def disconnect():
    """Gracefully close connection to server."""
    global client, connected
    if client:
        try:
            client.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass
    client = None
    connected = False
    add_message("[SYSTEM] Disconnected from server.")
    on_disconnected_ui_update()


def on_connected_ui_update():
    """Update UI controls when connected."""
    username_textbox.config(state=tk.DISABLED)
    username_button.config(state=tk.DISABLED)
    message_button.config(state=tk.NORMAL)
    message_textbox.config(state=tk.NORMAL)
    disconnect_button.config(state=tk.NORMAL)


def on_disconnected_ui_update():
    """Update UI controls when disconnected."""
    username_textbox.config(state=tk.NORMAL)
    username_button.config(state=tk.NORMAL)
    message_button.config(state=tk.DISABLED)
    message_textbox.config(state=tk.DISABLED)
    disconnect_button.config(state=tk.DISABLED)


def on_closing():
    """Called when the window is closing."""
    if connected:
        if messagebox.askyesno("Quit", "You are connected. Do you want to disconnect and quit?"):
            disconnect()
        else:
            return
    root.destroy()


# ---------- Build GUI ----------
root = tk.Tk()
root.geometry("600x600")
root.title("Messenger Client")
root.resizable(False, False)

root.grid_rowconfigure(0, weight=1)
root.grid_rowconfigure(1, weight=4)
root.grid_rowconfigure(2, weight=1)

top_frame = tk.Frame(root, width=600, height=100, bg=DARK_GREY)
top_frame.grid(row=0, column=0, sticky=tk.NSEW)

middle_frame = tk.Frame(root, width=600, height=400, bg=MEDIUM_GREY)
middle_frame.grid(row=1, column=0, sticky=tk.NSEW)

bottom_frame = tk.Frame(root, width=600, height=100, bg=DARK_GREY)
bottom_frame.grid(row=2, column=0, sticky=tk.NSEW)

username_label = tk.Label(top_frame, text="Enter username:", font=FONT, bg=DARK_GREY, fg=WHITE)
username_label.pack(side=tk.LEFT, padx=10, pady=15)

username_textbox = tk.Entry(top_frame, font=FONT, bg=MEDIUM_GREY, fg=WHITE, width=23, insertbackground=WHITE)
username_textbox.pack(side=tk.LEFT, pady=15)

username_button = tk.Button(top_frame, text="Join", font=FONT, bg=OCEAN_BLUE, fg=WHITE, command=connect)
username_button.pack(side=tk.LEFT, padx=12, pady=15)

disconnect_button = tk.Button(top_frame, text="Disconnect", font=("Helvetica", 12), bg="#A33", fg=WHITE, command=disconnect)
disconnect_button.pack(side=tk.LEFT, padx=8, pady=15)
disconnect_button.config(state=tk.DISABLED)

message_box = scrolledtext.ScrolledText(middle_frame, font=SMALL_FONT, bg=MEDIUM_GREY, fg=WHITE, height=26.5, state=tk.DISABLED)
message_box.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=6)

message_textbox = tk.Entry(bottom_frame, font=FONT, bg=MEDIUM_GREY, fg=WHITE, width=38, insertbackground=WHITE)
message_textbox.pack(side=tk.LEFT, padx=10, pady=15)
message_textbox.config(state=tk.DISABLED)

message_button = tk.Button(bottom_frame, text="Send", font=BUTTON_FONT, bg=OCEAN_BLUE, fg=WHITE, command=send_message)
message_button.pack(side=tk.LEFT, padx=10, pady=15)
message_button.config(state=tk.DISABLED)

# Bind Enter key to send when message box focused
def on_enter_pressed(event):
    if message_button['state'] == tk.NORMAL:
        send_message()
        return "break"
message_textbox.bind("<Return>", on_enter_pressed)

root.protocol("WM_DELETE_WINDOW", on_closing)

# Start the GUI
if __name__ == '__main__':
    root.mainloop()

