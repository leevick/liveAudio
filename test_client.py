#!/usr/bin/env python3
"""
Test client for the live audio streaming server
Connects to the stream and displays metadata updates
"""

import requests
import struct
import sys

def test_stream(url="http://localhost:5000/stream", duration=30):
    """
    Connect to stream and display metadata for specified duration
    
    Args:
        url: Stream URL
        duration: How long to listen in seconds
    """
    print(f"Connecting to {url}...")
    print("Requesting ICY metadata support...")
    
    # Request with ICY metadata support
    headers = {'Icy-MetaData': '1'}
    
    try:
        response = requests.get(url, headers=headers, stream=True, timeout=5)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to stream: {e}")
        return
    
    # Check if metadata is supported
    metaint = response.headers.get('icy-metaint')
    
    print("\n" + "="*60)
    print("STREAM INFORMATION")
    print("="*60)
    print(f"Stream Name: {response.headers.get('icy-name', 'N/A')}")
    print(f"Genre: {response.headers.get('icy-genre', 'N/A')}")
    print(f"Bitrate: {response.headers.get('icy-br', 'N/A')} kbps")
    print(f"Metadata Support: {'Yes' if metaint else 'No'}")
    if metaint:
        print(f"Metadata Interval: {metaint} bytes")
    print("="*60)
    
    if not metaint:
        print("\nServer does not support ICY metadata")
        return
    
    metaint = int(metaint)
    
    print("\nListening to stream... (Press Ctrl+C to stop)")
    print("-"*60)
    
    bytes_read = 0
    total_bytes = 0
    current_metadata = None
    
    try:
        for chunk in response.iter_content(chunk_size=1024):
            if not chunk:
                break
            
            for byte in chunk:
                if bytes_read < metaint:
                    # Audio data
                    bytes_read += 1
                    total_bytes += 1
                else:
                    # Metadata length (in 16-byte blocks)
                    meta_length = byte * 16
                    
                    if meta_length > 0:
                        # Read metadata
                        metadata_bytes = b''
                        meta_bytes_needed = meta_length
                        
                        # Continue reading from current chunk and additional chunks if needed
                        remaining_chunk = chunk[chunk.index(byte)+1:]
                        metadata_bytes += remaining_chunk[:meta_bytes_needed]
                        meta_bytes_needed -= len(metadata_bytes)
                        
                        # Read more if needed
                        while meta_bytes_needed > 0:
                            extra_chunk = next(response.iter_content(chunk_size=meta_bytes_needed), b'')
                            metadata_bytes += extra_chunk
                            meta_bytes_needed -= len(extra_chunk)
                        
                        # Parse metadata
                        try:
                            metadata_str = metadata_bytes.decode('latin1').rstrip('\x00')
                            if metadata_str != current_metadata:
                                current_metadata = metadata_str
                                # Extract StreamTitle
                                if 'StreamTitle=' in metadata_str:
                                    title = metadata_str.split("StreamTitle='")[1].split("';")[0]
                                    print(f"\n🎵 Now Playing: {title}")
                                    print(f"   [{total_bytes:,} bytes received]")
                        except Exception as e:
                            print(f"Error parsing metadata: {e}")
                    
                    bytes_read = 0
                    break
    
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    except Exception as e:
        print(f"\nError: {e}")
    
    print(f"\nTotal data received: {total_bytes:,} bytes ({total_bytes/1024/1024:.2f} MB)")

def test_api(base_url="http://localhost:5000"):
    """Test the API endpoints"""
    print("\n" + "="*60)
    print("TESTING API ENDPOINTS")
    print("="*60)
    
    # Test status endpoint
    try:
        print("\n1. Testing /status endpoint...")
        response = requests.get(f"{base_url}/status", timeout=5)
        response.raise_for_status()
        data = response.json()
        print(f"   Status: {data.get('status')}")
        if 'current_track' in data:
            track = data['current_track']
            print(f"   Current: {track.get('artist')} - {track.get('title')}")
            print(f"   Track {data.get('track_index', 0) + 1} of {data.get('playlist_size', 0)}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test playlist endpoint
    try:
        print("\n2. Testing /playlist endpoint...")
        response = requests.get(f"{base_url}/playlist", timeout=5)
        response.raise_for_status()
        data = response.json()
        print(f"   Total tracks: {data.get('total', 0)}")
        if data.get('tracks'):
            print(f"   First 3 tracks:")
            for track in data['tracks'][:3]:
                print(f"      {track['index']+1}. {track['artist']} - {track['title']}")
    except Exception as e:
        print(f"   Error: {e}")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Test the live audio streaming server')
    parser.add_argument('--url', default='http://localhost:5000', help='Base server URL')
    parser.add_argument('--stream-only', action='store_true', help='Only test streaming, not API')
    parser.add_argument('--api-only', action='store_true', help='Only test API, not streaming')
    parser.add_argument('--duration', type=int, default=30, help='How long to stream (seconds)')
    
    args = parser.parse_args()
    
    if not args.stream_only:
        test_api(args.url)
    
    if not args.api_only:
        print()
        test_stream(f"{args.url}/stream", args.duration)
