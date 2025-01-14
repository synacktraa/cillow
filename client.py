import cillow

client = cillow.Client.new(host="127.0.0.1", port=5556)

print(client.current_environment)

client.run_code("""
from PIL import Image, ImageDraw

img = Image.new('RGB', (400, 300), 'white')

draw = ImageDraw.Draw(img)
draw.rectangle([50, 50, 150, 150], fill='blue')
draw.ellipse([200, 50, 300, 150], fill='red')
draw.line([50, 200, 350, 200], fill='green', width=5)

img.show()
""")

client.disconnect()
