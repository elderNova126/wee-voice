import asyncio
import sys
import traceback
import logging
from datetime import datetime
from typing import Any

import pyaudio
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# ------------------------------------------------------
# Logging setup
# ------------------------------------------------------
def setup_logging():
    log_filename = f"chat_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    file_handler = logging.FileHandler(log_filename)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

# ------------------------------------------------------
# Example tool function
# ------------------------------------------------------
def get_user_name() -> str:
    """
    Retrieves and returns the name of the user.
    """
    return "Johnathan Wickerbasket"

# ------------------------------------------------------
# Compatibility for Python < 3.11
# ------------------------------------------------------
if sys.version_info < (3, 11, 0):
    import taskgroup, exceptiongroup
    asyncio.TaskGroup = taskgroup.TaskGroup
    asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup

# ------------------------------------------------------
# Audio configuration
# ------------------------------------------------------
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000   # Gemini input audio rate
RECEIVE_SAMPLE_RATE = 24000  # Gemini output audio rate
CHUNK_SIZE = 2048

# ------------------------------------------------------
# Gemini Realtime Client setup
# ------------------------------------------------------
client = genai.Client()  # GOOGLE_API_KEY must be in .env

MODEL = "gemini-2.5-flash-native-audio-preview-09-2025"
tools = [get_user_name]

CONFIG = {
    "response_modalities": ["AUDIO", "TEXT"],  # include text responses too
    "enable_input_transcription": True,        # 👈 enable transcription
    "tools": tools,
    "system_instruction": types.Content(parts=[
        types.Part(text="You are a helpful assistant named Aye-vah and answer in a friendly tone."),
        types.Part(text="Use the 'get_user_name' tool to retrieve the name of the user."),
    ]),
}


# ------------------------------------------------------
# Audio Loop Class
# ------------------------------------------------------
class AudioLoop:
    pya = pyaudio.PyAudio()

    def __init__(self):
        self.audio_in_queue = None
        self.out_queue = None
        self.session = None
        self.audio_stream = None

    async def listen_audio(self):
        """Capture microphone input and push chunks to out_queue."""
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
        kwargs = {"exception_on_overflow": False} if __debug__ else {}
        while True:
            data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)
            await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})

    async def send_realtime(self):
        """Send captured audio chunks to Gemini session."""
        while True:
            msg = await self.out_queue.get()
            await self.session.send_realtime_input(audio=msg)

    async def receive_audio(self):
        """
        Receives streamed responses from Gemini:
        - Transcriptions of your speech
        - Assistant's text and audio
        """
        transcription_file = open("transcriptions.txt", "a", encoding="utf-8")
        while True:
            turn = self.session.receive()
            async for response in turn:
                logger.debug(f"Raw event: {response}")

                # 🎙️ Show your speech transcription
                if hasattr(response, "input_transcript") and response.input_transcript:
                    logger.info(f"🗣️ You said: {response.input_transcript}")
                    transcription_file.write(f"{datetime.now()}: USER: {response.input_transcript}\n")

                # 🎧 Play Gemini’s audio responses
                if data := response.data:
                    self.audio_in_queue.put_nowait(data)
                    continue

                # 💬 Show Gemini’s text responses
                if text := response.text:
                    logger.info(f"🤖 Aye-vah: {text}")
                    transcription_file.write(f"{datetime.now()}: AYE-VAH: {text}\n")

                # 🛠️ Handle tool calls
                if function_call := response.tool_call:
                    func_responses = []
                    for call in function_call.function_calls:
                        if call.name == "get_user_name":
                            logger.info("Calling tool: get_user_name()")
                            func_response = types.FunctionResponse(
                                id=call.id,
                                name=call.name,
                                response={"user_name": get_user_name()},
                            )
                            func_responses.append(func_response)
                    await self.session.send_tool_response(function_responses=func_responses)

            # Clear queued audio if interrupted
            while not self.audio_in_queue.empty():
                self.audio_in_queue.get_nowait()

    async def play_audio(self):
        """Play assistant’s audio output."""
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
        """Main orchestrator."""
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


# ------------------------------------------------------
# Run the audio loop
# ------------------------------------------------------
if __name__ == "__main__":
    loop = AudioLoop()
    asyncio.run(loop.run())
