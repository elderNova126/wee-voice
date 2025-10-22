import asyncio
import sys
import traceback
import logging
from datetime import datetime
import os

import pyaudio
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Use Windows Proactor event loop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

load_dotenv()

# Suppress warnings from google_genai.types about non-text/non-data parts
# These warnings occur when the model returns structured responses with multiple parts
logging.getLogger('google_genai.types').setLevel(logging.ERROR)

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
    import taskgroup
    import exceptiongroup

    asyncio.TaskGroup = taskgroup.TaskGroup
    asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup
    # Provide a local ExceptionGroup name for except clauses below
    ExceptionGroup = exceptiongroup.ExceptionGroup
else:
    # On Python 3.11+ ExceptionGroup is a built-in
    ExceptionGroup = ExceptionGroup

# Configuration for pyaudio
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000  # Gemini models are trained on 16 kHz audio
RECEIVE_SAMPLE_RATE = 24000  # Receive audio is processed at 24 kHz
CHUNK_SIZE = 2048  # Send audio in chunks of 2048 bytes


class TurnComplete(Exception):
    pass


client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
MODEL = "gemini-2.5-flash-native-audio-preview-09-2025"
tools = [get_user_name]
CONFIG = {
    "response_modalities": ["AUDIO"], 
    "tools": tools, 
    "system_instruction": "You are a helpful assistant named Aye-vah and answer in a friendly tone. Use the 'get_user_name' tool to retrieve the name of the user.",
    "input_audio_transcription": {},
    "output_audio_transcription": {},
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
        
        self.history = []

    async def listen_audio(self):
        mic_info = self.pya.get_default_input_device_info()
        print(f"🎤 Using microphone: {mic_info['name']}")
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
        print("🎤 Listening... Speak now!")
        while True:
            data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)
            await self.out_queue.put({"data": data, "mime_type": f"audio/pcm;rate={SEND_SAMPLE_RATE}"})

    async def send_realtime(self):
        chunk_count = 0
        while True:
            msg = await self.out_queue.get()
            chunk_count += 1
            if chunk_count % 50 == 0:  # Log every 50 chunks to avoid spam
                print(f"📤 Sent {chunk_count} audio chunks")
            await self.session.send_realtime_input(audio=msg)

    async def receive_audio(self):
        "Background task to reads from the websocket and write pcm chunks to the output queue"
        print("📡 Connected to Gemini API, waiting for responses...")
        
        user_input_text = ""
        model_response_parts = []

        async for response in self.session.receive():
            # Debug: Log all response attributes
            print(f"\n🔍 Response type: {type(response)}")
            print(f"🔍 Response attributes: {dir(response)}")
            logger.info(response)
            
            if data := response.data:
                print(f"🔊 Received audio data: {len(data)} bytes")
                self.audio_in_queue.put_nowait(data)
                continue
            
            # Log assistant's text transcription
            if text := response.text:
                model_response_parts.append(types.Part(text=text))
                logger.info(f"ASSISTANT: {text}")
                print(f"\n🤖 ASSISTANT: {text}")
            
            # Check for user transcription in server_content
            if hasattr(response, 'server_content') and response.server_content:
                if hasattr(response.server_content, 'model_turn') and response.server_content.model_turn:
                    for part in response.server_content.model_turn.parts:
                        if hasattr(part, 'text') and part.text:
                            user_input_text += part.text
                            logger.info(f"USER: {part.text}")
                            print(f"\n👤 USER: {part.text}")
                # Check for turn_complete with user transcript
                if hasattr(response.server_content, 'turn_complete') and response.server_content.turn_complete:
                    # If you interrupt the model, it sends a turn_complete.
                    # For interruptions to work, we need to stop playback.
                    # So empty out the audio queue because it may have loaded
                    # much more audio than has played yet.
                    while not self.audio_in_queue.empty():
                        self.audio_in_queue.get_nowait()
            
            if function_call := response.tool_call:
                model_response_parts.append(types.Part(function_call=function_call))
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
                self.history.append(types.Content(role='tool', parts=[
                    part for fr in func_responses for part in fr.parts
                ]))
        
        if user_input_text:
            self.history.append(types.Content(role='user', parts=[types.Part(text=user_input_text)]))
        if model_response_parts:
            self.history.append(types.Content(role='model', parts=model_response_parts))

        raise TurnComplete

    async def play_audio(self):
        """Plays audio from the input queue."""
        # The first audio chunk is usually silence.
        # This is a good time to open the stream.
        stream = await asyncio.to_thread(
            self.pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
        )
        print("🔊 Audio playback ready")
        while True:
            bytestream = await self.audio_in_queue.get()
            await asyncio.to_thread(stream.write, bytestream)

    async def run(self):
        """Main loop to run the audio agent."""
        while True:
            try:
                print("Starting new conversation turn...")
                async with (
                    client.aio.live.connect(
                        model=MODEL, config=CONFIG, history=self.history
                    ) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session = session

                    # Create new queues for each turn
                    self.audio_in_queue = asyncio.Queue()
                    self.out_queue = asyncio.Queue(maxsize=5)

                    # Start tasks for this turn
                    tg.create_task(self.listen_audio())
                    tg.create_task(self.send_realtime())
                    tg.create_task(self.receive_audio())
                    tg.create_task(self.play_audio())

            except* TurnComplete:
                # This is the expected way a turn ends.
                logger.info("Turn complete.")
            except* Exception as eg:
                logger.error(f"An error occurred: {eg}")
                traceback.print_exception(eg)

            finally:
                if self.audio_stream and self.audio_stream.is_active():
                    self.audio_stream.stop_stream()
                if self.audio_stream:
                    self.audio_stream.close()
                # Reset audio stream for the next turn
                self.audio_stream = None
                logger.info("Cleaned up audio stream.")
                await asyncio.sleep(0.1)  # Wait a bit before restarting


if __name__ == "__main__":
    loop = AudioLoop()
    asyncio.run(loop.run())