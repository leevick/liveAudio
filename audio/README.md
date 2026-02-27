# Audio Files Directory

Place your audio files here for streaming.

## Supported Formats

- MP3 (.mp3)
- OGG Vorbis (.ogg)
- FLAC (.flac)
- M4A (.m4a)
- WAV (.wav)

## Example

```bash
# Copy your music files here
cp ~/Music/*.mp3 .

# Or download sample audio (example)
wget https://example.com/sample.mp3
```

## Notes

- Files will be played in alphabetical order
- The server will automatically detect and read metadata (artist, title)
- If no metadata is found, the filename will be used as the title
