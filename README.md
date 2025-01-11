# cillow

<p align="center">Code Interpreter Library</p>

---

<p align="center">
    <a href="https://img.shields.io/github/v/release/synacktraa/cillow">
        <img src="https://img.shields.io/github/v/release/synacktraa/cillow" alt="cillow version">
    </a>
    <a href="https://github.com/synacktraa/cillow/actions/workflows/main.yml">
        <img src="https://github.com/synacktraa/cillow/actions/workflows/main.yml/badge.svg" alt="cillow CI status">
    </a>
    <a href="https://codecov.io/gh/synacktraa/cillow">
        <img src="https://codecov.io/gh/synacktraa/cillow/branch/main/graph/badge.svg" alt="cillow codecov">
    </a>
    <a href="https://img.shields.io/github/license/synacktraa/cillow">
        <img src="https://img.shields.io/github/license/synacktraa/cillow" alt="cillow license">
    </a>
</p>

Cillow is an open-source library that enables you to execute AI-generated code in a controlled environment. The name "Cillow" follows the same naming convention as "Pillow" (Python Imaging Library), representing its role as a Code Interpreter Library.

It offers key features such as:

- **Environment Switching**: Easily switch between multiple python environments.
- **Automated Package Management**: Automatic installation of imported packages through `uv` or `pip`.
- **Functionality Patches**: Apply patches to limit the scope of AI-generated code, capture outputs like `stdout`, `stderr`, images, plots, etc., and more.

### Check Documentation

Visit [synacktra.is-a.dev/cillow](https://synacktra.is-a.dev/cillow/)

### Installation

```bash
pip install cillow
```

### Hosting a server

```python
import cillow

cillow.add_patches(
    cillow.prebuilt_patches.patch_stdout_stderr_write,
    cillow.prebuilt_patches.patch_matplotlib_pyplot_show,
    cillow.prebuilt_patches.patch_pillow_show,
)

if __name__ == "__main__":
    server = cillow.Server(
        port=5556, max_interpreters=2, interpreters_per_client=1
    )
    server.run()
```

### Running code through a client

```python
import cillow

client = cillow.Client.new(host="127.0.0.1", port=5556)

client.run_code("""
from PIL import Image, ImageDraw

img = Image.new('RGB', (400, 300), 'white')

draw = ImageDraw.Draw(img)
draw.rectangle([50, 50, 350, 250], outline='black', width=3)
draw.ellipse([100, 100, 300, 200], outline='purple', width=3)
draw.line([50, 250, 350, 250], fill='blue', width=3)

img.show()
""")
```

---

At the moment, Cillow only supports Python since it doesn't use Jupyter Kernel.

This project began as an exploration of [E2B](https://e2b.dev/)'s code interpreter. I implemented the Python interpreter from scratch using ZeroMQ, taking a different approach by adding features like environment switching and functionality patching. Seeing the potential in this project, I evolved it into a client-server architecture using threading and multiprocessing.
