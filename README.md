# Add STT to wazo-calld

A Wazo plugin that adds Speech-To-Text (STT) capabilities to wazo-calld with support for multiple engines.

## Features

- Real-time speech-to-text transcription of calls
- Multiple transcription engines supported:
  - Google Cloud Speech-to-Text
  - Voice AI Service (with optional AI agent responses)
- API to start/stop transcription on calls
- Events published on the Wazo message bus for each transcription
- Optional AI agent responses when using Voice AI Service

## Installation

### Engine-specific dependencies

For Google:

```
pip3 install google-cloud-speech
```

For Voice AI:

```
pip3 install websockets>=10.0
```

### To install plugin:

```
wazo-plugind-cli -c "install git https://github.com/sboily/wazo-hackathon-wazo-calld-module"
```

## Configuration

Edit the configuration file at `/etc/wazo-calld/conf.d/50-stt.yml`:

```yaml
enabled_plugins:
  stt: true
stt:
  engine: 'google'  # options: 'google', 'voice_ai'
  google_creds: /path/to/google-credentials.json
  voice_ai_uri: ws://localhost:8765
  use_ai: false  # Enable AI agent for voice_ai engine
  dump_dir: /tmp/stt
  ari_websocket_stream: ws://127.0.0.1:5039/ws
  language: fr_FR
  stasis: true
  workers: 10
```

## API Usage

### Start STT on a call

```
POST /api/calld/1.0/stt
```

Request body:
```json
{
  "call_id": "1234567.89",
  "use_ai": true  # Optional, only for voice_ai engine
}
```

### Stop STT on a call

```
DELETE /api/calld/1.0/stt/{call_id}
```

## Events

### STT events

Events are published on the Wazo message bus with the routing key `applications.stt.event`:

```json
{
  "call_id": "1234567.89",
  "result_stt": "Transcribed text here"
}
```

### AI response events (voice_ai engine only)

Events are published on the Wazo message bus with the routing key `applications.ai_response.event`:

```json
{
  "call_id": "1234567.89",
  "ai_response": "AI response text here"
}
```

## Voice AI Service

The Voice AI Service is a separate service that provides speech-to-text transcription and optional AI agent responses. The service must be running and accessible from the Wazo server.

The Voice AI Service protocol works as follows:

1. The client connects to the service via WebSocket
2. The client sends a configuration message:
   ```json
   {
     "type": "config",
     "language": "fr_FR",
     "use_ai": true,
     "sample_rate": 16000
   }
   ```
3. The client sends audio chunks
4. The service responds with transcription and AI responses:
   ```json
   {
     "type": "transcription",
     "text": "Transcribed text here"
   }
   ```
   ```json
   {
     "type": "ai_response",
     "text": "AI response text here"
   }
   ```

All AI responses are automatically published to the Wazo message bus and can be consumed by other applications.
