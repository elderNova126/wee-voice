import asyncio
import sys
import traceback
import inspect
from typing import Dict, Any
import logging
from datetime import datetime

import pyaudio
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# Set up logging
def setup_logging():
    log_filename = f"chat_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # File handler
    file_handler = logging.FileHandler(log_filename)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

# Basic function tool
def get_user_name() -> str:
    """
    Retrieves & returns the name of the user.

    Args:
        None

    Returns:
        A string containing the name of the user.
    """
    return "Johnathan Wickerbasket"


# For Python versions < 3.11, monkey-patch asyncio with TaskGroup and ExceptionGroup
# implementations from the taskgroup and exceptiongroup packages
if sys.version_info < (3, 11, 0):
    import taskgroup, exceptiongroup

    asyncio.TaskGroup = taskgroup.TaskGroup
    asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup

# Configuration for pyaudio
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000  # Gemini models are trained on 16 kHz audio
RECEIVE_SAMPLE_RATE = 24000  # Receive audio is processed at 24 kHz
CHUNK_SIZE = 2048  # Send audio in chunks of 2048 bytes


client = genai.Client()  # GOOGLE_API_KEY must be set as env variable in .env file
MODEL = "gemini-2.5-flash-preview-native-audio-dialog"
tools = [get_user_name]
CONFIG = {
    "response_modalities": ["AUDIO"], 
    "tools": tools, 
    "system_instruction": types.Content(parts=[
        types.Part(text="You are a helpful assistant named Aye-vah and answer in a friendly tone."),
        types.Part(text="Use the 'get_user_name' tool to retrieve the name of the user."),
        ])
}


class AudioLoop:
    pya = pyaudio.PyAudio()
    def __init__(self):
        self.audio_in_queue = None
        self.out_queue = None

        self.session = None

        self.audio_stream = None

        self.receive_audio_task = None
        self.play_audio_task = None


    async def listen_audio(self):
        mic_info = self.pya.get_default_input_device_info()
        self.audio_stream = await asyncio.to_thread(
            self.pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=SEND_SAMPLE_RATE,
            input=True,
            input_device_index=mic_info["index"],
            frames_per_buffer=CHUNK_SIZE,
        )
        if __debug__:
            kwargs = {"exception_on_overflow": False}
        else:
            kwargs = {}
        while True:
            data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)
            await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})

    async def send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send_realtime_input(audio=msg)

    async def receive_audio(self):
        "Background task to reads from the websocket and write pcm chunks to the output queue"
        while True:
            turn = self.session.receive()
            async for response in turn:
                logger.info(response)
                if data := response.data:
                    self.audio_in_queue.put_nowait(data)
                    continue
                if text := response.text:
                    logger.info(text)
                if function_call := response.tool_call:
                    func_responses = []
                    for call in function_call.function_calls:
                        if call.name == "get_user_name":
                            logger.info("Using function: get_user_name")
                            func_response = types.FunctionResponse(
                                id=call.id,
                                name=call.name,
                                response={"user_name": get_user_name()},
                            )
                            func_responses.append(func_response)
                    await self.session.send_tool_response(function_responses=func_responses)
                

            # If you interrupt the model, it sends a turn_complete.
            # For interruptions to work, we need to stop playback.
            # So empty out the audio queue because it may have loaded
            # much more audio than has played yet.
            while not self.audio_in_queue.empty():
                self.audio_in_queue.get_nowait()

    async def play_audio(self):
        stream = await asyncio.to_thread(
            self.pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
        )
        while True:
            bytestream = await self.audio_in_queue.get()
            await asyncio.to_thread(stream.write, bytestream)

    async def run(self):
        try:
            async with (
                client.aio.live.connect(model=MODEL, config=CONFIG) as session,
                asyncio.TaskGroup() as tg,
            ):
                self.session = session

                self.audio_in_queue = asyncio.Queue()
                self.out_queue = asyncio.Queue(maxsize=5)

                tg.create_task(self.listen_audio())
                tg.create_task(self.send_realtime())
                tg.create_task(self.receive_audio())
                tg.create_task(self.play_audio())
        except asyncio.CancelledError:
            pass
        except asyncio.ExceptionGroup as EG:
            if self.audio_stream:
                self.audio_stream.close()
            traceback.print_exception(EG)


if __name__ == "__main__":
    loop = AudioLoop()
    asyncio.run(loop.run())