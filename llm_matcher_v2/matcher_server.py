# matcher_server.py
# This contains the sever code and will import
# `process_request_with_chunking` from ollama_matcher.py

import sys
import tqdm
import json
import socket
import struct
import time

from ollama_matcher import process_request_with_chunking

BUFFER_SIZE = 65536

def handle_client(client_socket, client_address):
    """
    Handles a single client connection, processing multiple requests sequentially.

    Args:
        client_socket (socket.socket): The socket object for the client connection.
        client_address (tuple): A tuple (IP address, port number) of the client.
    """
    print(f"Accepted connection from {client_address[0]}:{client_address[1]}")
    connection_active = True
    while connection_active:
        try:
            # Step 1: Read length prefix (4 bytes)
            msg_length_bytes = client_socket.recv(4, socket.MSG_WAITALL) # MSG_WAITALL ensures all 4 bytes are received
            if not msg_length_bytes:
                print(f"[{client_address[0]}:{client_address[1]}] No further message length received. Client likely closed connection gracefully.")
                connection_active = False # Break out of the loop
                continue # Go to finally block

            # Unpack message length from 4 bytes
            msglen = struct.unpack('>I', msg_length_bytes)[0]
            print(f"[{client_address[0]}:{client_address[1]}] Expecting {msglen} bytes of data from Predictor.")

            # Step 2: Receive the actual payload in packets
            data_recv = b''
            progress = tqdm.tqdm(range(msglen), unit="B",
                                    desc=f"[{client_address[0]}:{client_address[1]}] Receiving Request",
                                    unit_scale=True, unit_divisor=1024, leave=False) # leave=False to clear bar on completion

            try:
                while len(data_recv) < msglen:
                    packet = client_socket.recv(min(BUFFER_SIZE, msglen - len(data_recv))) # Read up to remaining bytes or BUFFER_SIZE
                    if not packet:
                        # Client disconnected mid-receive
                        raise ConnectionError(f"[{client_address[0]}:{client_address[1]}] Connection to predictor lost while receiving data")
                    data_recv += packet
                    progress.update(len(packet))
            finally:
                progress.close() # Ensure progress bar is closed even on error

            # Verify if all of the data is received
            if len(data_recv) == msglen:
                print(f"[{client_address[0]}:{client_address[1]}] Predictor request received completely.")
            else:
                print(f"[{client_address[0]}:{client_address[1]}] Data received was incomplete or corrupted. Expected {msglen}, got {len(data_recv)}.")
                connection_active = False # Treat corrupted data as a reason to close connection
                continue

            # Step 3: Decode incoming payload into dict
            try:
                print(f"[{client_address[0]}:{client_address[1]}] Unpacking payload from Predictor.")
                request_data = json.loads(data_recv.decode("utf-8"))
            except json.JSONDecodeError as e:
                print(f"[{client_address[0]}:{client_address[1]}] Failed to decode Predictor payload (JSON error): {e}")
                connection_active = False # Treat as fatal for this request
                continue
            except Exception as e:
                print(f"[{client_address[0]}:{client_address[1]}] Unexpected error during payload decoding: {e}")
                connection_active = False
                continue

            # Step 4: Call the core logic
            start_time = time.time()
            # process_request_with_chunking should handle different request types
            response_data = process_request_with_chunking(request_data)
            end_time = time.time()
            elapsed_time = end_time - start_time

            # Dynamically determine the key and value for logging
            # Assumes response_data will have at least one key if successful
            matched_key = next(iter(response_data.keys()), "unknown_key")
            matched_value = response_data.get(matched_key, "N/A") # Default to N/A if key is missing

            print(f"[{client_address[0]}:{client_address[1]}] Matched '{matched_key}' to '{matched_value}' in {elapsed_time:.4f} seconds")
            # If you want to see the full JSON response in server logs:
            # print(f"[{client_address[0]}:{client_address[1]}] Sending Matcher response: {response_data}")

            # Step 5: Encode the response dictionary into a JSON byte string and send it back
            response_bytes = json.dumps(response_data).encode("utf-8")
            client_socket.sendall(struct.pack(">I", len(response_bytes)))
            client_socket.sendall(response_bytes)

        except (ConnectionError, ConnectionResetError, BrokenPipeError) as e:
            # These exceptions typically mean the client closed its end unexpectedly
            print(f"[{client_address[0]}:{client_address[1]}] Connection error with client: {e}")
            connection_active = False
        except struct.error as e:
            # Error in unpacking length, often indicates malformed send from client or partial read
            print(f"[{client_address[0]}:{client_address[1]}] Structural data error (e.g., length prefix): {e}")
            connection_active = False
        except Exception as e:
            # Catch any other unexpected errors during the request handling loop
            print(f"[{client_address[0]}:{client_address[1]}] An unexpected error occurred during client handling: {e}")
            connection_active = False
        finally:
            # This block runs whether there's an error or the loop completes (connection_active = False)
            if not connection_active: # Only print and close if the loop is actually ending
                print(f"[{client_address[0]}:{client_address[1]}] Closing connection with client.")
                client_socket.close()

def run_matcher(matcher_ip, matcher_port):
    """
    Sets up and runs a persistent TCP server that listens for incoming client connections.
    Each client connection is handled by `handle_client`, which can process multiple
    requests from that single connection.
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Allows immediate reuse of address
    server.bind((matcher_ip, matcher_port))
    server.listen(0) # Allow no backlog of connections
    print(f"Matcher is listening on {matcher_ip}:{matcher_port}")

    try:
        while True: # Server continuously accepts new client connections
            print("Waiting for a Predictor (client) to connect...")
            client_socket, client_address = server.accept()
            handle_client(client_socket, client_address)
    except KeyboardInterrupt:
        print("\nMatcher server shutting down via KeyboardInterrupt.")
    except Exception as e:
        print(f"An unexpected error occurred in the main server loop: {e}")
    finally:
        print("Server socket closed.")
        server.close()

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python matcher_server.py <host_ip> <port>")
        print("Example: python matcher_server.py 0.0.0.0 5000")
        sys.exit(1)

    HOST = sys.argv[1]
    PORT = int(sys.argv[2])

    run_matcher(HOST, PORT)