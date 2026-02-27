# AAC Streaming Quick Start Guide

This guide shows how to configure the server to stream AAC audio with ICY metadata.

## Why AAC?

- **Better Quality**: AAC provides better audio quality than MP3 at the same bitrate
- **Smaller Files**: More efficient compression
- **Modern Standard**: Used by Apple Music, YouTube, and most streaming services
- **Wide Support**: Supported by all modern media players and browsers

## Setup for AAC Streaming

### 1. Install ffmpeg (required for AAC encoding)

```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Fedora
sudo dnf install ffmpeg
```

### 2. Configure for AAC Output

Edit `config.json`:

```json
{
  "audio_dir": "audio",
  "host": "0.0.0.0",
  "port": 5000,
  "bitrate": 96,
  "chunk_size": 4096,
  "output_format": "aac",
  "metadata_mode": "auto"
}
```

**Recommended AAC Bitrates:**
- **64 kbps**: Voice/podcasts
- **96 kbps**: Good quality (recommended)
- **128 kbps**: High quality
- **192 kbps**: Very high quality

### 3. Add Your Audio Files

Place any audio files (MP3, FLAC, WAV, OGG, etc.) in the `audio/` directory:

```bash
cp ~/Music/*.mp3 audio/
# or
cp ~/Music/*.flac audio/
```

The server will automatically transcode them to AAC.

### 4. Start the Server

```bash
python stream_server.py
```

You should see:
```
Output Format: AAC @ 96kbps
Stream URL: http://localhost:5000/stream
```

## Listening to AAC Stream

### VLC Media Player
```bash
vlc http://localhost:5000/stream
```

### mpv
```bash
mpv http://localhost:5000/stream
```

### Web Browser
Open: `http://localhost:5000`

### ffplay
```bash
ffplay -nodisp http://localhost:5000/stream
```

## Verify ICY Metadata

Check that metadata is working:

```bash
# Using test client
python test_client.py

# Or using curl
curl -H "Icy-MetaData: 1" http://localhost:5000/stream -v | head -c 1000
```

Look for these headers:
- `icy-metaint: 16000` - Metadata interval
- `Content-Type: audio/aac` - AAC format
- `icy-br: 96` - Bitrate

## Metadata Configuration

The server supports three metadata modes configured via `metadata_mode` in config.json:

### `auto` (Default)
Metadata is sent only if the client requests it with `Icy-MetaData: 1` header.
```json
{
  "metadata_mode": "auto"
}
```
**Best for**: General use, maximum compatibility

### `forced`
Metadata is always sent to all clients, regardless of their request.
```json
{
  "metadata_mode": "forced"
}
```
**Best for**: Ensuring all clients get track info, custom players, debugging

### `disable`
Metadata is never sent, even if client requests it.
```json
{
  "metadata_mode": "disable"
}
```
**Best for**: Background music, reducing overhead, testing pure audio stream

## Performance Notes

### CPU Usage
- **Direct streaming** (no transcoding): Very low CPU usage
- **With transcoding**: Moderate CPU usage (depends on bitrate and number of clients)
- Each client gets its own transcoding stream

### Quality vs Size
AAC at 96 kbps ≈ MP3 at 128 kbps in quality

## Troubleshooting

### "ffmpeg not found" error
Install ffmpeg as shown in step 1 above.

### No sound / corrupted audio
- Verify ffmpeg is installed: `ffmpeg -version`
- Check server logs for transcoding errors
- Try a lower bitrate (64 or 96 kbps)

### High CPU usage
- Reduce bitrate in config.json
- Reduce number of simultaneous clients
- Use source files that match output format (AAC/M4A files don't need transcoding)

### Metadata not showing
- Ensure client supports ICY metadata (VLC, mpv, Winamp do)
- Check `/status` endpoint to verify metadata is being read
- Try connecting with the test client

## Advanced Configuration

### Using Pre-encoded AAC Files

To avoid transcoding overhead, use AAC source files:

1. Convert your library to AAC:
```bash
for file in *.mp3; do
    ffmpeg -i "$file" -c:a aac -b:a 96k "${file%.mp3}.m4a"
done
```

2. Move AAC files to audio directory:
```bash
mv *.m4a audio/
```

3. Server will stream directly without transcoding

### Custom AAC Parameters

For advanced users, you can modify the `_transcode_audio` method in `stream_server.py` to add custom ffmpeg parameters like:
- `-profile:a aac_low` - AAC-LC profile (most compatible)
- `-ar 44100` - Sample rate
- `-ac 2` - Stereo channels

## Example Use Cases

### Podcast Streaming
```json
{
  "bitrate": 64,
  "output_format": "aac",
  "metadata_mode": "forced"
}
```

### Music Streaming (balanced)
```json
{
  "bitrate": 96,
  "output_format": "aac",
  "metadata_mode": "auto"
}
```

### High-Quality Music
```json
{
  "bitrate": 192,
  "output_format": "aac",
  "metadata_mode": "auto"
}
```
