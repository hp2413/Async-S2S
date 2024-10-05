# Copyright 2023 LiveKit, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncContextManager

from agents import tts, utils

from .log import logger
from .models import TTSModels, TTSVoices
from .utils import AsyncAzureADTokenProvider


from pathlib import Path
import edge_tts  # type: ignore


EDGE_TTS_SAMPLE_RATE = 24000  # Default Edge TTS sample rate
EDGE_TTS_CHANNELS = 1         # Mono

@dataclass
class _TTSOptions:
    model: TTSModels
    voice: TTSVoices
    speed: float


class TTS(tts.TTS):
    def __init__(
        self,
        *,
        model: TTSModels = "edge-tts-1",
        voice: TTSVoices = "en-US-AvaMultilingualNeural",
        speed: float = 1.0,
        cache_dir: str = "./cache",
    ) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(
                streaming=False,
            ),
            sample_rate=EDGE_TTS_SAMPLE_RATE,
            num_channels=EDGE_TTS_CHANNELS,
        )

        self._opts = _TTSOptions(
            model=model,
            voice=voice,
            speed=speed,
        )

        self.cache_dir = Path(cache_dir)
        self.temp_audio_file = "temp"
        self.file_extension = "mp3"

        if not self.cache_dir.exists():
            self.cache_dir.mkdir(parents=True)

    def synthesize(self, text: str) -> "ChunkedStream":
        return ChunkedStream(text, self._opts)


class ChunkedStream(tts.ChunkedStream):
    def __init__(
        self,
        text: str,
        opts: _TTSOptions,
    ) -> None:
        super().__init__()
        self._opts, self._text = opts, text
        

    @utils.log_exceptions(logger=logger)
    async def _main_task(self):
        communicate = edge_tts.Communicate(self._text, self._opts.voice)
        request_id = utils.shortuuid()
        segment_id = utils.shortuuid()
        decoder = utils.codecs.Mp3StreamDecoder()
        audio_bstream = utils.audio.AudioByteStream(
            sample_rate=EDGE_TTS_SAMPLE_RATE,
            num_channels=EDGE_TTS_CHANNELS,
        )

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                data = chunk["data"]
                for frame in decoder.decode_chunk(data):
                    for frame in audio_bstream.write(frame.data):
                        self._event_ch.send_nowait(
                            tts.SynthesizedAudio(
                                request_id=request_id,
                                segment_id=segment_id,
                                frame=frame,
                            )
                        )

        for frame in audio_bstream.flush():
            self._event_ch.send_nowait(
                tts.SynthesizedAudio(
                    request_id=request_id, segment_id=segment_id, frame=frame
                )
            )
