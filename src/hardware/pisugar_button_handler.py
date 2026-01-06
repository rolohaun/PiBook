"""
PiSugar2 button handler using Unix socket IPC.
Receives button events from PiSugar2 custom shell commands.
PORTABILITY: Works on any system with Unix socket support
"""

import logging
import socket
import threading
import os
from typing import Callable, Dict, Optional


class PiSugarButtonHandler:
    """
    Handle PiSugar2 button events via Unix socket IPC
    """
    
    def __init__(self, socket_path: str = "/tmp/pibook-button.sock"):
        """
        Initialize button handler

        Args:
            socket_path: Path to Unix socket for IPC
        """
        self.logger = logging.getLogger(__name__)
        self.socket_path = socket_path
        self.callbacks: Dict[str, Callable] = {}
        self.running = False
        self.server_thread: Optional[threading.Thread] = None
        self.server_socket: Optional[socket.socket] = None
    
    def register_callback(self, action: str, callback: Callable):
        """
        Register a callback for a button action

        Args:
            action: Action name (e.g., 'next_page', 'prev_page', 'menu')
            callback: Function to call when action is triggered
        """
        self.callbacks[action] = callback
        self.logger.info(f"Registered PiSugar button callback for '{action}'")
    
    def start(self):
        """Start the socket server thread"""
        if self.running:
            self.logger.warning("PiSugar button handler already running")
            return
        
        # Remove existing socket file if it exists
        try:
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
        except Exception as e:
            self.logger.error(f"Failed to remove existing socket: {e}")
            return
        
        # Start server thread
        self.running = True
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        self.logger.info(f"PiSugar button handler started on {self.socket_path}")
    
    def stop(self):
        """Stop the socket server"""
        self.running = False
        
        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        # Remove socket file
        try:
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
        except:
            pass
        
        self.logger.info("PiSugar button handler stopped")
    
    def _run_server(self):
        """Run the Unix socket server (runs in thread)"""
        try:
            # Create Unix socket
            self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.server_socket.bind(self.socket_path)
            self.server_socket.listen(5)
            self.server_socket.settimeout(1.0)  # Allow periodic checks of self.running
            
            self.logger.info(f"Socket server listening on {self.socket_path}")
            
            while self.running:
                try:
                    # Accept connection
                    conn, _ = self.server_socket.accept()
                    
                    # Receive data
                    data = conn.recv(1024).decode().strip()
                    
                    # Close connection
                    conn.close()
                    
                    # Process command
                    if data:
                        self._handle_command(data)
                
                except socket.timeout:
                    # Timeout is expected, continue loop
                    continue
                except Exception as e:
                    if self.running:
                        self.logger.error(f"Socket server error: {e}")
        
        except Exception as e:
            self.logger.error(f"Failed to start socket server: {e}")
        
        finally:
            if self.server_socket:
                self.server_socket.close()
    
    def _handle_command(self, command: str):
        """
        Handle received command

        Args:
            command: Command string (e.g., 'next_page', 'prev_page')
        """
        self.logger.info(f"PiSugar button: {command}")
        
        if command in self.callbacks:
            try:
                self.callbacks[command]()
            except Exception as e:
                self.logger.error(f"Error executing callback for '{command}': {e}")
        else:
            self.logger.warning(f"No callback registered for '{command}'")
    
    def trigger_action(self, action: str):
        """
        Manually trigger an action (for testing)

        Args:
            action: Action name to trigger
        """
        self._handle_command(action)
