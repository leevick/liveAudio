# Metadata Mode Configuration Guide

The `metadata_mode` configuration option controls when ICY metadata is sent to clients.

## Overview

ICY metadata is embedded information about the currently playing track (Artist - Title) that is injected into the audio stream at regular intervals. This allows media players to display "Now Playing" information.

## Configuration

Set in `config.json`:

```json
{
  "metadata_mode": "auto"  // Options: "auto", "forced", "disable"
}
```

## Mode Details

### `auto` (Recommended Default)

**Behavior**: Metadata is sent only if the client explicitly requests it via the `Icy-MetaData: 1` HTTP header.

**When to use**:
- General purpose streaming
- Maximum compatibility with all clients
- Standard Icecast/SHOUTcast behavior

**Example**:
```json
{
  "output_format": "aac",
  "bitrate": 96,
  "metadata_mode": "auto"
}
```

**How clients connect**:
- VLC, mpv, Winamp: Automatically request metadata ✓
- Basic HTTP clients: No metadata (but stream still works) ✓
- Web browsers: May or may not request metadata

---

### `forced` (Always Send)

**Behavior**: Metadata is always sent to all clients, regardless of whether they requested it or not.

**When to use**:
- Ensuring all clients receive track information
- Custom/proprietary players that don't send `Icy-MetaData` header
- Debugging metadata issues
- When you want to guarantee metadata delivery

**Example**:
```json
{
  "output_format": "mp3",
  "bitrate": 128,
  "metadata_mode": "forced"
}
```

**Advantages**:
✓ Guaranteed metadata for all clients
✓ Simplifies client implementation (no need to request)
✓ Good for controlled environments

**Disadvantages**:
✗ Clients that don't support ICY protocol may have issues
✗ Slightly higher bandwidth usage
✗ May cause problems with strict HTTP clients

---

### `disable` (Never Send)

**Behavior**: Metadata is never sent, even if the client explicitly requests it.

**When to use**:
- Background music where track info isn't important
- Reducing server overhead
- Testing pure audio stream without metadata
- Compatibility with clients that have metadata parsing bugs
- Lowest possible latency

**Example**:
```json
{
  "output_format": "aac",
  "bitrate": 64,
  "metadata_mode": "disable"
}
```

**Advantages**:
✓ Slightly lower bandwidth usage (no metadata overhead)
✓ Pure audio stream
✓ Avoids metadata parsing issues
✓ Minimal processing overhead

**Disadvantages**:
✗ No "Now Playing" information
✗ Clients can't display track/artist

---

## How Metadata Works

### Technical Details

1. **Interval**: Metadata is injected every 16,000 bytes by default
2. **Format**: ICY protocol (Icecast/SHOUTcast standard)
3. **Content**: `StreamTitle='Artist - Title';`
4. **Encoding**: Latin-1 encoding, padded to 16-byte blocks

### Bandwidth Impact

Metadata adds minimal overhead:
- Metadata chunk: ~50-100 bytes every 16KB
- Overhead: Less than 1% of total bandwidth

### Example Stream Pattern

```
[Audio Data: 16000 bytes]
[Metadata: "StreamTitle='Artist - Song';"]
[Audio Data: 16000 bytes]
[Metadata: "StreamTitle='Artist - Song';"]
...
```

## Testing Metadata

### Check Current Mode

```bash
curl http://localhost:5000/status
```

Returns:
```json
{
  "status": "playing",
  "metadata_mode": "auto",
  ...
}
```

### Test Metadata Delivery

#### Test with metadata request:
```bash
curl -H "Icy-MetaData: 1" http://localhost:5000/stream -v 2>&1 | grep -i icy
```

Should show (if metadata enabled):
```
< icy-metaint: 16000
< icy-name: Live Audio Stream
< icy-br: 96
```

#### Test without metadata request:
```bash
curl http://localhost:5000/stream -v 2>&1 | grep -i icy
```

- `auto` mode: No `icy-metaint` header
- `forced` mode: Shows `icy-metaint` header anyway
- `disable` mode: Never shows `icy-metaint`

### Using Test Client

```bash
python test_client.py
```

This will show real-time metadata updates if they're being sent.

## Use Case Examples

### Radio Station
```json
{
  "metadata_mode": "forced",
  "output_format": "mp3",
  "bitrate": 128
}
```
Ensures all listeners see track info.

### Personal Music Server
```json
{
  "metadata_mode": "auto",
  "output_format": "aac",
  "bitrate": 96
}
```
Compatible with all clients, metadata on request.

### Background/Ambient Music
```json
{
  "metadata_mode": "disable",
  "output_format": "aac",
  "bitrate": 64
}
```
No metadata needed, lowest overhead.

### Development/Testing
```json
{
  "metadata_mode": "forced",
  "output_format": "mp3",
  "bitrate": 128
}
```
Always see metadata for debugging.

## Troubleshooting

### Metadata not showing in player

**If using `auto` mode**:
- Verify your player supports ICY metadata (VLC, mpv, Winamp do)
- Check server logs to see if client requested metadata
- Try `forced` mode to rule out client issues

**If using `forced` mode**:
- Check player's metadata display settings
- Some players need to reconnect after server restart
- Verify with test client: `python test_client.py`

**If using `disable` mode**:
- This is expected behavior - metadata is intentionally disabled

### Client connection issues

**Problem**: Client can't connect or stream is corrupted

**Solution**: 
- Try `auto` mode - most compatible
- Some strict HTTP clients don't support ICY protocol
- Check client logs for protocol errors

### Performance issues

**Problem**: Server using too much resources

**Solution**:
- `disable` mode has lowest overhead
- Metadata overhead is minimal (~1%), but every bit helps
- Transcoding has much larger impact than metadata

## Summary

| Mode | Metadata Sent | Use Case | Compatibility |
|------|---------------|----------|---------------|
| **auto** | Only if requested | General purpose | Best |
| **forced** | Always | Ensure delivery | Good |
| **disable** | Never | No metadata needed | Best |

**Recommendation**: Use `auto` unless you have a specific reason to use another mode.
