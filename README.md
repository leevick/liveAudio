# Live Audio Streaming Server

A Python-based HTTP audio streaming server with Icecast metadata support. Streams audio files (MP3, OGG, FLAC, etc.) with embedded metadata using the ICY protocol.

## Features

- 🎵 **Multiple Format Support**: MP3, OGG, FLAC, M4A, WAV
- � **Real-time Transcoding**: Convert to AAC, MP3, or OGG on-the-fly
- �📡 **Icecast/SHOUTcast Protocol**: ICY metadata for displaying current track info
- 🔄 **Continuous Streaming**: Automatically loops through playlist
- 📊 **REST API**: Status and playlist endpoints
- 🎧 **Universal Compatibility**: Works with VLC, Winamp, iTunes, web browsers, and more
- ⚙️ **Configurable**: Easy JSON configuration

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

**For transcoding support, install ffmpeg:**

```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Fedora
sudo dnf install ffmpeg
```

### 2. Add Audio Files

Create an `audio` directory and add your audio files:

```bash
mkdir audio
# Copy your MP3, OGG, or other audio files to the audio directory
cp /path/to/your/music/*.mp3 audio/
```

### 3. Run the Server

```bash
python stream_server.py
```

The server will start on `http://localhost:5000` by default.

## Usage

### Listening to the Stream

#### Using VLC Media Player
```bash
vlc http://localhost:5000/stream
```

#### Using mpv
```bash
mpv http://localhost:5000/stream
```

#### Using curl (save to file)
```bash
curl http://localhost:5000/stream > output.mp3
```

#### In Web Browser
Open `http://localhost:5000` and use the built-in audio player, or directly access:
```
http://localhost:5000/stream
```

### API Endpoints

#### Stream Endpoint
- **URL**: `/stream`
- **Method**: GET
- **Description**: Main audio stream with ICY metadata
- **Headers**: 
  - Set `Icy-MetaData: 1` to receive metadata updates

#### Status Endpoint
- **URL**: `/status`
- **Method**: GET
- **Returns**: JSON with current track information
```json
{
  "status": "playing",
  "current_track": {
    "title": "Song Name",
    "artist": "Artist Name"
  },
  "playlist_size": 10,
  "track_index": 3,
  "output_format": "aac",
  "bitrate": 128,
  "metadata_mode": "auto"
}
```

#### Playlist Endpoint
- **URL**: `/playlist`
- **Method**: GET
- **Returns**: JSON with complete playlist
```json
{
  "tracks": [
    {
      "index": 0,
      "filename": "song.mp3",
      "title": "Song Name",
      "artist": "Artist Name"
    }
  ],
  "total": 10
}
```

## Configuration

Edit `config.json` to customize server settings:

```json
{
  "audio_dir": "audio",      // Directory containing audio files
  "host": "0.0.0.0",         // Server host (0.0.0.0 for all interfaces)
  "port": 5000,              // Server port
  "bitrate": 128,            // Stream bitrate in kbps
  "chunk_size": 4096,        // Chunk size for streaming
  "output_format": "aac",    // Output format: "aac", "mp3", or "ogg"
  "metadata_mode": "auto"    // Metadata mode: "auto", "forced", or "disable"
}
```

### Output Formats

- **`aac`**: AAC audio in ADTS container - best quality/size ratio, modern codec
- **`mp3`**: MP3 audio - universal compatibility
- **`ogg`**: OGG Vorbis - open source, good quality

**Note**: If output format differs from source files, the server will transcode in real-time using ffmpeg.

### Metadata Modes

- **`auto`** (default): ICY metadata sent only if client requests it via `Icy-MetaData: 1` header
- **`forced`**: Always send ICY metadata to all clients, regardless of their request
- **`disable`**: Never send ICY metadata, even if client requests it

**Use Cases**:
- `auto`: Best for general purpose streaming, compatible with all clients
- `forced`: Ensures metadata is always available, useful for custom clients or debugging
- `disable`: Reduces overhead when metadata is not needed (e.g., background music)

## How It Works

### Real-time Transcoding

When `output_format` is set to a format different from your source files, the server automatically transcodes audio on-the-fly using ffmpeg:

1. Server detects input file format (MP3, FLAC, WAV, etc.)
2. If format differs from `output_format`, ffmpeg transcodes in real-time
3. Transcoded audio is streamed with ICY metadata inserted at regular intervals
4. No temporary files created - everything happens in memory

### ICY Protocol

The server implements the Icecast/SHOUTcast ICY protocol, which injects metadata into the audio stream at regular intervals (every 16,000 bytes by default). This allows compatible media players to display the current track information while playing.

### Metadata Extraction

The server uses the `mutagen` library to extract metadata (title, artist) from audio files. It supports:
- ID3 tags (MP3)
- Vorbis comments (OGG)
- Other tag formats via mutagen

### Stream Flow

1. Client connects to `/stream` endpoint
2. Server checks if client supports ICY metadata (`Icy-MetaData` header)
3. Server streams audio files sequentially from the playlist
4. Every 16,000 bytes, metadata is injected (if supported)
5. When playlist ends, it loops back to the beginning

## Advanced Usage

### Running on Different Port

```bash
# Edit config.json and change port to 8080
python stream_server.py
```

### Accessing from Other Devices

Make sure `host` is set to `0.0.0.0` in `config.json`, then access from other devices using your server's IP:

```
http://YOUR_SERVER_IP:5000/stream
```

### Testing with curl

Check if metadata is working:
```bash
curl -H "Icy-MetaData: 1" http://localhost:5000/stream --output /dev/null -v
```

Look for the `icy-metaint` header in the response.

## Troubleshooting

### No audio files found
- Make sure audio files are in the directory specified in `config.json` (default: `audio/`)
- Check that files have supported extensions (.mp3, .ogg, .m4a, .flac, .wav)

### Can't connect to stream
- Check if the server is running
- Verify firewall settings allow connections on the specified port
- Make sure the port isn't already in use

### Metadata not showing
- Ensure your media player supports ICY metadata
- VLC, mpv, and most modern players support it
- Check the `/status` endpoint to verify metadata is being read correctly

## Requirements

- Python 3.7+
- Flask 3.0.0
- mutagen 1.47.0
- pydub 0.25.1

## License

MIT License - Feel free to use and modify as needed.

## Contributing

Contributions welcome! Feel free to submit issues or pull requests.
