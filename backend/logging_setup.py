import logging
import logging.handlers
import sys
import os
import queue
import atexit

def setup_async_logging():
    """
    Configure non-blocking asynchronous logging using QueueHandler/QueueListener.
    This prevents disk I/O from blocking the main asyncio event loop.
    """
    _base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(_base_dir, "backend", "data")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "app.log")

    # 1. Create the actual handlers (File & Stream)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    # 2. Create a Queue and a QueueListener
    # The QueueListener runs in a separate internal thread
    log_queue = queue.Queue(-1) # Infinite queue
    queue_handler = logging.handlers.QueueHandler(log_queue)
    
    listener = logging.handlers.QueueListener(
        log_queue, 
        file_handler, 
        stream_handler, 
        respect_handler_level=True
    )
    
    # 3. Start the listener
    listener.start()
    
    # Register cleanup to stop listener on exit
    atexit.register(listener.stop)

    # 4. Configure Root Logger to use QueueHandler ONLY
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remove existing handlers to avoid duplicates
    if root_logger.handlers:
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            
    root_logger.addHandler(queue_handler)
    
    # 5. [Optional] Add a separate debug handler if needed (also async via queue? or separate?)
    # For simplicity, we route everything through the queue.
    # If specific debug files are needed, add them to the listener.

    print(f"Async Logging Initialized. Logs writing to: {log_file}")
    return listener
