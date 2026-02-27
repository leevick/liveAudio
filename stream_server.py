#!/usr/bin/env python3
"""
Live Audio Streaming Server with Icecast Metadata Support
Streams audio files (mp3, ogg, etc.) via HTTP with ICY protocol metadata
Supports transcoding to AAC, MP3, or OGG formats
"""

import os
import time
import json
import threading
import subprocess
import io
from pathlib import Path
from flask import Flask, Response, request
from mutagen import File as MutagenFile
from mutagen.mp3 import MP3
from mutagen.oggvorbis import OggVorbis
import struct

app = Flask(__name__)

class AudioStreamer:
    def __init__(self, audio_dir, bitrate=128, chunk_size=4096, output_format='mp3', metadata_mode='auto'):
        self.audio_dir = Path(audio_dir)
        self.bitrate = bitrate
        self.chunk_size = chunk_size
        self.output_format = output_format.lower()
        self.metadata_mode = metadata_mode.lower()
        self.playlist = []
        self.current_track_index = 0
        self.clients = []
        self.lock = threading.Lock()
        
        # Validate output format
        self.supported_outputs = ['mp3', 'aac', 'ogg']
        if self.output_format not in self.supported_outputs:
            raise ValueError(f"Output format must be one of {self.supported_outputs}")
        
        # Validate metadata mode
        self.supported_metadata_modes = ['auto', 'forced', 'disable']
        if self.metadata_mode not in self.supported_metadata_modes:
            raise ValueError(f"Metadata mode must be one of {self.supported_metadata_modes}")
        
        # Check if ffmpeg is available
        self.ffmpeg_available = self._check_ffmpeg()
        if not self.ffmpeg_available:
            print("Warning: ffmpeg not found. Transcoding disabled. Install with: apt-get install ffmpeg")
        
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
    
    def _check_ffmpeg(self):
        """Check if ffmpeg is available"""
        try:
            subprocess.run(['ffmpeg', '-version'], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL, 
                         check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def get_output_mime_type(self):
        """Get MIME type for output format"""
        mime_types = {
            'mp3': 'audio/mpeg',
            'aac': 'audio/aac',
            'ogg': 'audio/ogg'
        }
        return mime_types.get(self.output_format, 'audio/mpeg')
    
    def should_enable_metadata(self, client_request):
        """Determine if metadata should be enabled based on mode and client request
        
        Args:
            client_request: Boolean indicating if client requested metadata (Icy-MetaData header)
        
        Returns:
            Boolean indicating if metadata should be enabled
        """
        if self.metadata_mode == 'forced':
            return True
        elif self.metadata_mode == 'disable':
            return False
        else:  # auto
            return client_request
    
    def _needs_transcoding(self, file_path):
        """Check if file needs transcoding"""
        file_ext = file_path.suffix.lower().lstrip('.')
        
        # AAC files might be in m4a container
        if self.output_format == 'aac':
            return file_ext not in ['m4a', 'aac']
        
        return file_ext != self.output_format
    
    def _transcode_audio(self, file_path):
        """Transcode audio file to desired output format using ffmpeg"""
        codec_map = {
            'mp3': 'libmp3lame',
            'aac': 'aac',
            'ogg': 'libvorbis'
        }
        
        format_map = {
            'mp3': 'mp3',
            'aac': 'adts',  # AAC ADTS format for streaming
            'ogg': 'ogg'
        }
        
        codec = codec_map[self.output_format]
        out_format = format_map[self.output_format]
        
        # Build ffmpeg command
        cmd = [
            'ffmpeg',
            '-i', str(file_path),
            '-vn',  # No video
            '-acodec', codec,
            '-b:a', f'{self.bitrate}k',
            '-f', out_format,
            'pipe:1'  # Output to stdout
        ]
        
        # Start ffmpeg process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=self.chunk_size
        )
        
        return process
        
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
        print(f"New client connected. Metadata: {metadata_enabled}, Output: {self.output_format}")
        
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
            
            # Determine if transcoding is needed
            needs_transcode = self._needs_transcoding(current_file)
            
            # Read and stream the file
            try:
                if needs_transcode and self.ffmpeg_available:
                    # Stream with transcoding
                    print(f"  Transcoding to {self.output_format}...")
                    process = self._transcode_audio(current_file)
                    
                    try:
                        while True:
                            # Read chunk from ffmpeg
                            chunk = process.stdout.read(self.chunk_size)
                            if not chunk:
                                break
                            
                            # Handle metadata insertion
                            if metadata_enabled and bytes_since_metadata + len(chunk) >= metadata_interval:
                                # Split chunk at metadata point
                                bytes_to_meta = metadata_interval - bytes_since_metadata
                                yield chunk[:bytes_to_meta]
                                
                                # Insert metadata
                                icy_meta = self.create_icy_metadata(metadata['title'], metadata['artist'])
                                yield icy_meta
                                
                                # Yield remaining chunk
                                remaining = chunk[bytes_to_meta:]
                                if remaining:
                                    yield remaining
                                    bytes_since_metadata = len(remaining)
                                else:
                                    bytes_since_metadata = 0
                            else:
                                yield chunk
                                if metadata_enabled:
                                    bytes_since_metadata += len(chunk)
                    finally:
                        process.terminate()
                        process.wait()
                else:
                    # Stream without transcoding (direct file read)
                    if needs_transcode:
                        print(f"  Warning: File needs transcoding but ffmpeg is not available")
                    
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
    client_requested_metadata = request.headers.get('Icy-MetaData', '0') == '1'
    
    # Determine if metadata should be enabled based on mode
    icy_metadata = streamer.should_enable_metadata(client_requested_metadata)
    
    # Get MIME type based on output format
    mime_type = streamer.get_output_mime_type()
    
    # Create response with appropriate headers
    response = Response(
        streamer.stream_audio(metadata_enabled=icy_metadata),
        mimetype=mime_type,
        headers={
            'icy-name': 'Live Audio Stream',
            'icy-genre': 'Various',
            'icy-url': request.host_url,
            'icy-pub': '1',
            'icy-br': str(streamer.bitrate),
            'Cache-Control': 'no-cache, no-store',
            'Connection': 'close',
            'Content-Type': mime_type,
        }
    )
    
    # Add metadata interval header if metadata is enabled
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
            "track_index": streamer.current_track_index,
            "output_format": streamer.output_format,
            "bitrate": streamer.bitrate,
            "metadata_mode": streamer.metadata_mode
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
            "bitrate": 128,
            "output_format": "mp3",
            "metadata_mode": "auto"
        }
        # Save default config
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"Created default config.json")
    
    # Initialize streamer
    streamer = AudioStreamer(
        audio_dir=config.get('audio_dir', 'audio'),
        bitrate=config.get('bitrate', 128),
        output_format=config.get('output_format', 'mp3'),
        metadata_mode=config.get('metadata_mode', 'auto')
    )
    
    # Start Flask server
    host = config.get('host', '0.0.0.0')
    port = config.get('port', 5000)
    
    print(f"\n{'='*60}")
    print(f"Live Audio Streaming Server Starting...")
    print(f"{'='*60}")
    print(f"Output Format: {streamer.output_format.upper()} @ {streamer.bitrate}kbps")
    print(f"Metadata Mode: {streamer.metadata_mode}")
    print(f"Stream URL: http://localhost:{port}/stream")
    print(f"Status API: http://localhost:{port}/status")
    print(f"Playlist API: http://localhost:{port}/playlist")
    print(f"{'='*60}\n")
    
    app.run(host=host, port=port, threaded=True)

if __name__ == '__main__':
    main()
