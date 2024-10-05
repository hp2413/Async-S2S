import asyncio
import logging
import edge_tts
from  Credentials.keys import local_sst_base_url, ollama_base_url, openai_api_key
from  agents import AutoSubscribe, JobContext, WorkerOptions, cli, llm
from  pipeline import VoicePipelineAgent
from  plugins import  openai
from  livekit.plugins import silero

logger = logging.getLogger("test-voice-assistant")

# This function is the entrypoint for the agent.
async def entrypoint(ctx: JobContext):
    # Create an initial chat context with a system prompt
    initial_ctx = llm.ChatContext().append(
        role="system",
        text=(
            "You are a voice assistant created by LiveKit. Your interface with users will be voice. "
            "You should use short and concise responses, and avoiding usage of unpronouncable punctuation."
        ),
    )

    # Connect to the LiveKit room
    # indicating that the agent will only subscribe to audio tracks
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    assistant = VoicePipelineAgent(
        chat_ctx=initial_ctx,
        vad=silero.VAD.load(),
        stt=openai.STT(base_url=local_sst_base_url, model="Systran/faster-distil-whisper-large-v3", api_key = openai_api_key),
        llm=openai.LLM.with_ollama(base_url=ollama_base_url, model="llama3.1:latest"),
        tts=openai.TTS()
    )

    # Start the voice assistant with the LiveKit room
    assistant.start(ctx.room)

    await asyncio.sleep(1)

    # Greets the user with an initial message
    await assistant.say("Hey, how can I help you today?", allow_interruptions=True)


if __name__ == "__main__":
    # Initialize the worker with the entrypoint
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
