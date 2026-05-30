#!/bin/bash

source .venv/bin/activate
# yt-dlp-ejs ships the JS challenge solver YouTube now requires for format/
# caption extraction. It needs a JS runtime on PATH (node or deno); see README.
pip install -U yt-dlp yt-dlp-ejs

if [ "$1" = "online" ]; then
  time python main.py --speech-to-text gemini --model-size small news
else
  time python main.py news
fi