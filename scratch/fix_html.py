import shutil, os

# Backup the corrupted file first
shutil.copy('static/index.html', 'static/index.html.bak')
print('Backup saved to static/index.html.bak')

with open('static/index.html', 'rb') as f:
    data = f.read()

text = data.decode('latin-1')

# The file has "|| 'Spark'" injected before every real character.
# Split on the marker and take the first char from each part (skip leading empty part).
marker = "|| 'Spark'"
parts = text.split(marker)

# parts[0] is empty string (before first marker), parts[1:] each start with the real char
real_html = ''.join(p[0] if p else '' for p in parts[1:])

print('Reconstructed HTML length:', len(real_html))
print('First 200 chars:', real_html[:200])

# Write back as UTF-8
with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(real_html)

print('Done! static/index.html restored.')
