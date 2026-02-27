#!/usr/bin/env python3
"""
Live Audio Streaming Server with Icecast Metadata Support
Streams audio files (mp3, ogg, etc.) via HTTP with ICY protocol metadata
"""

import os
import time
import json
import threading
from pathlib import Path
from flask import Flask, Response, request
from mutagen import File as MutagenFile
from mutagen.mp3 import MP3
from mutagen.oggvorbis import OggVorbis
import struct

app = Flask(__name__)

class AudioStreamer:
    def __init__(self, audio_dir, bitrate=128, chunk_size=4096):
        self.audio_dir = Path(audio_dir)
        self.bitrate = bitrate
        self.chunk_size = chunk_size
        self.playlist = []
        self.current_track_index = 0
        self.clients = []
        self.lock = threading.Lock()
        
        # Load playlist
        self.load_playlist()
        
    def load_playlist(self):
        """Load all supported audio files from directory"""
        supported_formats = ['.mp3', '.ogg', '.m4a', '.flac', '.wav']
        self.playlist = []
        
        if not self.audio_dir.exists():
            print(f"Warning: Audio directory '{self.audio_dir}' does not exist")
            return
            
        for file in sorted(self.audio_dir.rglob('*')):
            if file.suffix.lower() in supported_formats and file.is_file():
                self.playlist.append(file)
        
        print(f"Loaded {len(self.playlist)} tracks from {self.audio_dir}")
        
    def get_metadata(self, file_path):
        """Extract metadata from audio file"""
        try:
            audio = MutagenFile(file_path)
            if audio is None:
                return {"title": file_path.stem, "artist": "Unknown"}
            
            title = None
            artist = None
            
            # Try different tag formats
            if hasattr(audio, 'tags') and audio.tags:
                # MP3 ID3 tags
                if 'TIT2' in audio.tags:
                    title = str(audio.tags['TIT2'])
                elif 'title' in audio.tags:
                    title = str(audio.tags['title'][0]) if isinstance(audio.tags['title'], list) else str(audio.tags['title'])
                
                if 'TPE1' in audio.tags:
                    artist = str(audio.tags['TPE1'])
                elif 'artist' in audio.tags:
                    artist = str(audio.tags['artist'][0]) if isinstance(audio.tags['artist'], list) else str(audio.tags['artist'])
            
            # Fallback to filename
            if not title:
                title = file_path.stem
            if not artist:
                artist = "Unknown Artist"
                
            return {"title": title, "artist": artist}
        except Exception as e:
            print(f"Error reading metadata from {file_path}: {e}")
            return {"title": file_path.stem, "artist": "Unknown"}
    
    def create_icy_metadata(self, title, artist):
        """Create ICY metadata chunk"""
        # Format: StreamTitle='Artist - Title';
        metadata_str = f"StreamTitle='{artist} - {title}';"
        
        # Metadata must be in 16-byte blocks
        metadata_length = len(metadata_str)
        # Calculate padding needed
        padding = 16 - (metadata_length % 16) if metadata_length % 16 != 0 else 0
        metadata_str += '\0' * padding
        
        # First byte is length in 16-byte blocks
        length_byte = (len(metadata_str) // 16).to_bytes(1, byteorder='big')
        
        return length_byte + metadata_str.encode('latin1', errors='replace')
    
    def stream_audio(self, metadata_enabled=True):
        """Generator function that yields audio data with optional metadata"""
        print(f"New client connected. Metadata: {metadata_enabled}")
        
        if not self.playlist:
            yield b"No audio files found in playlist directory\n"
            return
        
        # Metadata interval in bytes (standard is 16000)
        metadata_interval = 16000 if metadata_enabled else 0
        bytes_since_metadata = 0
        
        while True:
            # Get current track
            try:
                current_file = self.playlist[self.current_track_index]
            except IndexError:
                # Reset to beginning if we've run out
                self.current_track_index = 0
                current_file = self.playlist[0]
            
            # Get metadata
            metadata = self.get_metadata(current_file)
            print(f"Now playing: {metadata['artist']} - {metadata['title']}")
            
            # Read and stream the file
            try:
                with open(current_file, 'rb') as f:
                    while True:
                        # Read chunk
                        if metadata_enabled and bytes_since_metadata + self.chunk_size >= metadata_interval:
                            # Read only up to metadata point
                            bytes_to_read = metadata_interval - bytes_since_metadata
                            chunk = f.read(bytes_to_read)
                            if not chunk:
                                break
                            
                            yield chunk
                            
                            # Insert metadata
                            icy_meta = self.create_icy_metadata(metadata['title'], metadata['artist'])
                            yield icy_meta
                            
                            bytes_since_metadata = 0
                        else:
                            chunk = f.read(self.chunk_size)
                            if not chunk:
                                break
                            
                            yield chunk
                            
                            if metadata_enabled:
                                bytes_since_metadata += len(chunk)
            
            except Exception as e:
                print(f"Error streaming file {current_file}: {e}")
            
            # Move to next track
            with self.lock:
                self.current_track_index = (self.current_track_index + 1) % len(self.playlist)
            
            # Small delay between tracks (optional)
            time.sleep(0.1)

# Global streamer instance
streamer = None

@app.route('/stream')
def stream():
    """Main streaming endpoint"""
    global streamer
    
    if streamer is None or not streamer.playlist:
        return "No audio files available. Please add audio files to the 'audio' directory.", 503
    
    # Check if client supports ICY metadata
    icy_metadata = request.headers.get('Icy-MetaData', '0') == '1'
    
    # Create response with appropriate headers
    response = Response(
        streamer.stream_audio(metadata_enabled=icy_metadata),
        mimetype='audio/mpeg',
        headers={
            'icy-name': 'Live Audio Stream',
            'icy-genre': 'Various',
            'icy-url': request.host_url,
            'icy-pub': '1',
            'icy-br': str(streamer.bitrate),
            'Cache-Control': 'no-cache, no-store',
            'Connection': 'close',
            'Content-Type': 'audio/mpeg',
        }
    )
    
    # Add metadata interval header if client supports it
    if icy_metadata:
        response.headers['icy-metaint'] = '16000'
    
    return response

@app.route('/status')
def status():
    """Get current stream status"""
    if streamer is None:
        return {"status": "not initialized"}, 503
    
    if not streamer.playlist:
        return {"status": "no tracks", "message": "No audio files in playlist"}, 200
    
    try:
        current_file = streamer.playlist[streamer.current_track_index]
        metadata = streamer.get_metadata(current_file)
        
        return {
            "status": "playing",
            "current_track": metadata,
            "playlist_size": len(streamer.playlist),
            "track_index": streamer.current_track_index
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

@app.route('/playlist')
def playlist():
    """Get current playlist"""
    if streamer is None:
        return {"tracks": []}, 200
    
    tracks = []
    for i, file in enumerate(streamer.playlist):
        metadata = streamer.get_metadata(file)
        tracks.append({
            "index": i,
            "filename": file.name,
            "title": metadata['title'],
            "artist": metadata['artist']
        })
    
    return {"tracks": tracks, "total": len(tracks)}

@app.route('/')
def index():
    """Landing page with server info"""
    return """
    <html>
    <head><title>Live Audio Stream</title></head>
    <body>
        <h1>Live Audio Streaming Server</h1>
        <h2>Endpoints:</h2>
        <ul>
            <li><a href="/stream">/stream</a> - Main audio stream (ICY protocol)</li>
            <li><a href="/status">/status</a> - Current track status (JSON)</li>
            <li><a href="/playlist">/playlist</a> - View playlist (JSON)</li>
        </ul>
        <h2>How to listen:</h2>
        <p>Open in media player (VLC, mpv, etc.):</p>
        <code>vlc http://localhost:5000/stream</code>
        <br><br>
        <audio controls>
            <source src="/stream" type="audio/mpeg">
            Your browser does not support the audio element.
        </audio>
    </body>
    </html>
    """

def main():
    global streamer
    
    # Load configuration
    config_file = Path('config.json')
    if config_file.exists():
        with open(config_file) as f:
            config = json.load(f)
    else:
        config = {
            "audio_dir": "audio",
            "host": "0.0.0.0",
            "port": 5000,
            "bitrate": 128
        }
        # Save default config
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"Created default config.json")
    
    # Initialize streamer
    streamer = AudioStreamer(
        audio_dir=config.get('audio_dir', 'audio'),
        bitrate=config.get('bitrate', 128)
    )
    
    # Start Flask server
    host = config.get('host', '0.0.0.0')
    port = config.get('port', 5000)
    
    print(f"\n{'='*60}")
    print(f"Live Audio Streaming Server Starting...")
    print(f"{'='*60}")
    print(f"Stream URL: http://localhost:{port}/stream")
    print(f"Status API: http://localhost:{port}/status")
    print(f"Playlist API: http://localhost:{port}/playlist")
    print(f"{'='*60}\n")
    
    app.run(host=host, port=port, threaded=True)

if __name__ == '__main__':
    main()
