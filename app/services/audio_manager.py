import asyncio
from typing import Optional, Any
import threading

class AudioStreamManager:
    def __init__(self):
        self.current_stream: Optional[Any] = None
        self.stream_lock = asyncio.Lock()
        self.should_stop = threading.Event()
    
    async def start_new_stream(self, audio_data: bytes):
        async with self.stream_lock:
            if self.current_stream:
                self.should_stop.set()
                await asyncio.sleep(0.1)
            
            self.should_stop.clear()
            self.current_stream = audio_data
    
    async def stop_current_stream(self):
        async with self.stream_lock:
            if self.current_stream:
                self.should_stop.set()
                self.current_stream = None