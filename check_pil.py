import math
import requests
import json
import os
import io

try:
    from PIL import Image
    has_pil = True
except ImportError:
    has_pil = False

print(f"PIL available: {has_pil}")
