import os

print("Building all-in-one standalone HTML file...", flush=True)

with open("index.html", "r", encoding="utf-8") as f:
    html = f.read()

with open("style.css", "r", encoding="utf-8") as f:
    css = f.read()

with open("libs/three.min.js", "r", encoding="utf-8") as f:
    three_js = f.read()

with open("libs/OrbitControls.js", "r", encoding="utf-8") as f:
    controls_js = f.read()

with open("annadel_data.js", "r", encoding="utf-8") as f:
    data_js = f.read()

with open("app.js", "r", encoding="utf-8") as f:
    app_js = f.read()

# Replace CSS link with inline <style>
html = html.replace('<link rel="stylesheet" href="style.css">', f'<style>\n{css}\n</style>')

# Remove external script tags and ServiceWorker for standalone
scripts_to_remove = [
    '<script src="libs/three.min.js"></script>',
    '<script src="libs/OrbitControls.js"></script>',
    '<script src="annadel_data.js"></script>',
    '<script src="app.js"></script>'
]

for s in scripts_to_remove:
    html = html.replace(s, '')

# Inject all scripts inline before </body>
combined_scripts = f"""
  <script>
  {three_js}
  </script>
  <script>
  {controls_js}
  </script>
  <script>
  {data_js}
  </script>
  <script>
  {app_js}
  </script>
"""

html = html.replace('</body>', f'{combined_scripts}\n</body>')

with open("annadel_standalone.html", "w", encoding="utf-8") as f:
    f.write(html)

size_mb = os.path.getsize("annadel_standalone.html") / (1024 * 1024)
print(f"Generated annadel_standalone.html successfully! Size: {size_mb:.2f} MB", flush=True)
