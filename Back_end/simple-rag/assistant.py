import pickle

from agents import AutoSubscribe, JobContext, WorkerOptions, cli, llm
from pipeline import VoicePipelineAgent
from plugins import openai, rag, silero

annoy_index = rag.annoy.AnnoyIndex.load("vdb_data")  # see build_data.py

embeddings_dimension = 1536
with open("my_data.pkl", "rb") as f:
    paragraphs_by_uuid = pickle.load(f)


async def entrypoint(ctx: JobContext):
    async def _enrich_with_rag(
        assistant: VoicePipelineAgent, chat_ctx: llm.ChatContext
    ):
        # locate the last user message and use it to query the RAG model
        # to get the most relevant paragraph
        # then provide that as additional context to the LLM
        user_msg = chat_ctx.messages[-1]
        user_embedding = await openai.create_embeddings(
            input=[user_msg.content],
            model="text-embedding-3-small",
            dimensions=embeddings_dimension,
        )

        result = annoy_index.query(user_embedding[0].embedding, n=1)[0]
        paragraph = paragraphs_by_uuid[result.userdata]
        user_msg.content = (
            "Context:\n" + paragraph + "\n\nUser question: " + user_msg.content
        )

    initial_ctx = llm.ChatContext().append(
        role="system",
        text=(
            "You are a voice assistant created by LiveKit. Your interface with users will be voice. "
            "You should use short and concise responses, and avoiding usage of unpronouncable punctuation."
            "Use the provided context to answer the user's question if needed."
        ),
    )

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    assistant = VoicePipelineAgent(
        chat_ctx=initial_ctx,
        vad=silero.VAD.load(),
        stt=deepgram.STT(),
        llm=openai.LLM(),
        tts=openai.TTS(),
        before_llm_cb=_enrich_with_rag,
    )

    assistant.start(ctx.room)

    await assistant.say("Hey, how can I help you today?", allow_interruptions=True)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
