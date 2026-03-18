# storage.py Summary

## Overview

`storage.py` contains a `Storage` class that works as an in-memory key-value store.
It stores data in Python dictionaries and includes TTL support.

This implementation does not save data to disk.
Values are kept only in memory while the process is running.

## Internal State

The class manages two dictionaries:

- `self._data`: stores actual key-value pairs
- `self._expires_at`: stores expiration timestamps for keys

It also uses:

- `self._time_func`: injected time function for easier testing

## Methods

### `set(key, value) -> str`

- Saves `value` under `key`
- Removes existing TTL metadata for that key
- Returns `"OK"`

### `get(key) -> str | None`

- Checks whether the key is expired
- Automatically deletes expired keys
- Returns the stored value
- Returns `None` if the key does not exist

### `delete(key) -> bool`

- Checks whether the key is expired
- Deletes the key if it exists
- Removes its TTL metadata too
- Returns `True` on success
- Returns `False` if the key does not exist

### `expire(key, seconds) -> bool`

- Sets a TTL on an existing key
- Stores the expiration time in `self._expires_at`
- Returns `True` if the key exists
- Returns `False` if the key does not exist

### `ttl(key) -> int`

Returns TTL using Redis-style integer rules:

- `-2`: the key does not exist
- `-1`: the key exists but has no expiration time
- `0` or higher: remaining lifetime in seconds

Before calculating TTL, expired keys are removed automatically.

## Expiration Flow

Expiration handling is centered around `_purge_if_expired(key)`.

This helper:

- reads the key's expiration time
- compares it with the current time
- deletes the key from both dictionaries if expired

This helper is called by:

- `get()`
- `delete()`
- `expire()`
- `ttl()`

## Test-Friendly Design

`Storage` accepts an optional `time_func` in the constructor:

```python
storage = Storage(time_func=fake_time)
```

This makes TTL behavior easy to test without waiting in real time.

## Current Characteristics

- In-memory only
- Simple structure
- TTL stored separately from values
- Expired keys are cleaned lazily on access
- Easy to extend with more Redis-like commands later
