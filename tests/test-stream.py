#!/usr/bin/env python3
import requests
import json
import sys

url = "http://localhost:8000/requirements/stream"

try:
    response = requests.post(url, stream=True, timeout=300)
    response.raise_for_status()
    print("Streaming requirements (press Ctrl+C to stop):\n")

    buffer = ""
    for chunk in response.iter_content(chunk_size=1, decode_unicode=True):
        if chunk:
            buffer += chunk
            if "\n\n" in buffer:
                events, buffer = buffer.split("\n\n", 1)
                for line in events.split("\n"):
                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            data = json.loads(data_str)
                            if 'token' in data:
                                print(data['token'], end='', flush=True)
                            elif 'done' in data:
                                print("\n\n✅ Streaming completed.")
                                if 'error' in data:
                                    print(f"⚠️ Warning: {data['error']}")
                                sys.exit(0)
                        except json.JSONDecodeError:
                            pass
    print("\n\n⚠️ Connection closed without 'done' signal.")
except KeyboardInterrupt:
    print("\n\n⏹️ Interrupted by user.")
except requests.exceptions.RequestException as e:
    print(f"❌ Error: {e}")