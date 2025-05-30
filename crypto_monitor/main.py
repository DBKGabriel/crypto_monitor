#!/usr/bin/env python3
import signal
import sys
import time
import atexit

# Local imports
from config_crypto_monitor import parse_arguments, APP_VERSION
from models.trade_model import TradeModel
from models.order_book_model import OrderBookModel
from models.database import DatabaseManager
from views.console_view import ConsoleView
from views.gui_view import GuiView
from views.OrderBook_3dVisualization import VisualizationView
from controllers.command_controller import CommandController
from controllers.websocket_controller import WebSocketController

class CryptoMonitorApp:
    def __init__(self, args=None):
        """
        Initialize the Crypto Monitor application.
        
        Args:
            args: Command line arguments
        """
        # Parse command line arguments
        self.args = args or parse_arguments()
        
        # Extract configuration
        self.db_name = self.args.db_name
        self.symbols = [s.upper() for s in self.args.symbols]
        self.enable_viz = self.args.viz
        self.batch_size = self.args.batch_size
        
        # Initialize models
        self.trade_model = TradeModel(self.symbols)
        self.order_book_model = OrderBookModel(self.symbols)
        self.db_manager = DatabaseManager(
            self.db_name, 
            batch_size=self.batch_size
        )
        
        # Initialize views - pass the version to ConsoleView
        self.console_view = ConsoleView(version=APP_VERSION)
        self.gui_view = GuiView()
        self.visualizer = VisualizationView(self.symbols)
        
        # Initialize controllers
        self.ws_controller = WebSocketController(
            self.trade_model,
            self.order_book_model,
            self.db_manager,
            self.console_view,
            self.visualizer
        )
        
        self.cmd_controller = CommandController(
            self.trade_model,
            self.gui_view,
            self.console_view,
            self.visualizer,
            self.ws_controller  # Pass WebSocket controller
        )
        
        # Override the database manager accessor
        self.cmd_controller.get_database_manager = lambda: self.db_manager
        
        # Setup signal handlers
        self._setup_signal_handlers()
        
        # Register cleanup handler
        atexit.register(self.cleanup)
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(sig, frame):
            print("\nReceived interrupt signal. Shutting down...")
            self.cleanup()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def start(self):
        """Start the application."""
        self.console_view.print_info(f"Starting Cryptocurrency Market Monitor with database: {self.db_name}", persistent=True)
        self.console_view.print_info(f"Tracking symbols: {', '.join(self.symbols)}", persistent=True)
        
        # Start command listener
        self.cmd_controller.start_listener()
        
        # Start WebSocket connection
        self.ws_controller.connect()
        
        # Start visualization if enabled
        if self.enable_viz:
            self.console_view.print_info("Starting 3D visualization...")
            success = self.visualizer.start()
            if success:
                self.console_view.print_success("Visualization started. Open http://127.0.0.1:8050 in your browser.")
            else:
                self.console_view.print_error("Failed to start visualization. Make sure you have required packages installed.")
        
        # Print initial help
        # self.console_view.print_info("Type 'help' for available commands, 'status' for connection info, or 'reconnect' to reset connection.")
        self.console_view.print_info("Type 'help' for available commands, 'status' for connection info, or 'reconnect' to reset connection.", persistent=True)
        
        # Keep the main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.console_view.print_info("Shutting down...")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources."""
        self.console_view.print_info("Cleaning up application resources...")
        
        # Stop command controller
        if hasattr(self, 'cmd_controller'):
            try:
                self.cmd_controller.stop()
            except Exception as e:
                print(f"Error stopping command controller: {e}")
        
        # Close WebSocket
        if hasattr(self, 'ws_controller'):
            try:
                self.ws_controller.close()
            except Exception as e:
                print(f"Error closing WebSocket: {e}")
        
        # Stop visualization
        if hasattr(self, 'visualizer') and self.visualizer.running:
            try:
                self.visualizer.stop()
            except Exception as e:
                print(f"Error stopping visualization: {e}")
        
        # Flush and close database
        if hasattr(self, 'db_manager'):
            try:
                self.console_view.print_info("Flushing remaining database records...")
                self.db_manager.flush()
                self.db_manager.close()
                self.console_view.print_success("Database closed successfully.")
            except Exception as e:
                print(f"Error closing database: {e}")
        
        self.console_view.print_info("Application shutdown complete.")

if __name__ == "__main__":
    app = CryptoMonitorApp()
    app.start()