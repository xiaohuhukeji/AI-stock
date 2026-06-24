#!/usr/bin/env python3
"""
Simple SSL SMTP Proxy
将非SSL连接转发到QQ邮箱SSL SMTP服务器
"""

import socket
import ssl
import threading

LOCAL_HOST = '0.0.0.0'
LOCAL_PORT = 2525

REMOTE_HOST = 'smtp.qq.com'
REMOTE_PORT = 465

def handle_client(client_socket, client_address):
    print(f"Connection from {client_address}")
    
    remote_socket = None
    
    try:
        remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_socket.settimeout(30)
        
        context = ssl.create_default_context()
        remote_ssl = context.wrap_socket(remote_socket, server_hostname=REMOTE_HOST)
        remote_ssl.connect((REMOTE_HOST, REMOTE_PORT))
        
        print(f"Connected to {REMOTE_HOST}:{REMOTE_PORT}")
        
        def forward(source, destination, name):
            try:
                while True:
                    data = source.recv(4096)
                    if not data:
                        break
                    destination.sendall(data)
            except:
                pass
            finally:
                try:
                    source.close()
                except:
                    pass
                try:
                    destination.close()
                except:
                    pass
        
        t1 = threading.Thread(target=forward, args=(client_socket, remote_ssl, "C->S"))
        t2 = threading.Thread(target=forward, args=(remote_ssl, client_socket, "S->C"))
        
        t1.daemon = True
        t2.daemon = True
        
        t1.start()
        t2.start()
        
        t1.join()
        t2.join()
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if remote_socket:
            try:
                remote_socket.close()
            except:
                pass
        try:
            client_socket.close()
        except:
            pass
        print(f"Connection closed: {client_address}")

def main():
    print(f"SMTP Proxy starting on {LOCAL_HOST}:{LOCAL_PORT}")
    print(f"Forwarding to {REMOTE_HOST}:{REMOTE_PORT}")
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((LOCAL_HOST, LOCAL_PORT))
    server_socket.listen(5)
    
    print("SMTP Proxy is ready. Waiting for connections...")
    
    while True:
        try:
            client_socket, client_address = server_socket.accept()
            client_socket.settimeout(30)
            
            t = threading.Thread(target=handle_client, args=(client_socket, client_address))
            t.daemon = True
            t.start()
        except KeyboardInterrupt:
            print("\nSMTP Proxy stopping...")
            break
        except Exception as e:
            print(f"Server error: {e}")
    
    server_socket.close()

if __name__ == '__main__':
    main()
