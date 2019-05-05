# -*- coding: utf-8 -*-
# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import os
import functools
import logging

from concurrent.futures import ThreadPoolExecutor
from ari.exceptions import ARINotFound
from websocket import WebSocketApp
from google.cloud import speech
from google.cloud.speech import enums
from google.cloud.speech import types

logger = logging.getLogger(__name__)


class SttService(object):

    def __init__(self, config, ari, notifier):
        self._config = config
        self._notifier = notifier
        self._ari = ari
        self._threadpool = ThreadPoolExecutor(max_workers=self._config["stt"]["workers"])
        self._speech_client = speech.SpeechClient.from_service_account_file(
            config["stt"]["google_creds"])
        self._streaming_config = types.StreamingRecognitionConfig(
            config=types.RecognitionConfig(
                encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code=self._config["stt"]["language"]))

        self._buffers = {}
        self._current_calls = {}
        if self._config["stt"].get("dump_dir"):
            try:
                os.makedirs(self._config["stt"]["dump_dir"])
            except OSError:
                pass

    def start(self, channel):
        logger.critical("channel: %s", channel)
        call_thread = self._threadpool.submit(self._handle_call, channel)
        self._current_calls.update({call_id: call_thread})
        logger.critical("thread started")

    def stop(self, call_id):
        call = self._current_calls.get(call_id)
        call.cancel()
        return call.done()

    def get_channel_by_id(self, channel_id):
        return self._ari.channels.get(channelId=channel_id)

    def _open_dumb(self, channel):
        if self._config["stt"].get("dump_dir"):
            return open("%s/wazo-stt-dump-%s.pcm" % (
                self._config["stt"]["dump_dir"],
                channel.id), "wb+")

    def _handle_call(self, channel):
        dump = self._open_dumb(channel)
        ws = WebSocketApp(self._config["stt"]["ari_websocket_stream"],
                          header={"Channel-ID": channel.id},
                          subprotocols=["stream-channel"],
                          on_error=self._on_error,
                          on_message=functools.partial(self._on_message,
                                                       channel=channel,
                                                       dump=dump),
                          on_close=functools.partial(self._on_close,
                                                     channel=channel,
                                                     dump=dump)
                          )
        logger.critical("websocket client started")
        ws.run_forever()

    def _on_error(self, ws, error):
        logger.error("stt websocket error: %s", error)

    def _on_close(self, ws, channel, dump):
        self._send_buffer(channel, dump)
        dump.close()

    def _on_message(self, ws, message, channel=None, dump=None):
        chunk = self._buffers.setdefault(channel.id, b'') + message
        self._buffers[channel.id] = chunk

        if len(chunk) < 1024 * 64:
            return

        self._send_buffer(channel, dump)

    def _send_buffer(self, channel, dump):
        chunk = self._buffers.pop(channel.id, None)
        logger.critical("_send_buffer: chunk len: %s",
                        len(chunk) if chunk is not None else None)
        if not chunk:
            return

        if dump:
            dump.write(chunk)

        request = types.StreamingRecognizeRequest(audio_content=chunk)

        responses = list(self._speech_client.streaming_recognize(
            self._streaming_config, [request]))

        logger.critical("responses: %d" % len(responses))
        for response in responses:
            results = list(response.results)
            logger.critical("results: %d" % len(results))
            for result in results:
                if result.is_final:
                    last_stt = result.alternatives[0].transcript
                    logger.critical("result last stt: %s", last_stt)

                    try:
                        all_stt = (
                            channel.getChannelVar(
                                variable="X_WAZO_STT")['value'] +
                            last_stt
                        )
                    except ARINotFound:
                        all_stt = last_stt
                    channel.setChannelVar(variable="X_WAZO_STT",
                                          value=all_stt[-1020:])
                    self._notifier.publish_stt(channel.id, last_stt)
