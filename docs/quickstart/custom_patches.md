This guide will show you how to write custom patches for your own use cases.

Cillow comes with prebuilt patches to capture real-time streaming outputs generated during code execution so they can be redirected to the client when added. Currently, the following patches are available:

- [`patch_stdout_stderr_write`](../sdk_reference/prebuilt_patches.md#patch_stdout_stderr_write): Captures `sys.stdout` and `sys.stderr` writes.
- [`patch_matplotlib_pyplot_show`](../sdk_reference/prebuilt_patches.md#patch_matplotlib_pyplot_show): Captures `matplotlib.pyplot.show()` calls.
- [`patch_pillow_show`](../sdk_reference/prebuilt_patches.md#patch_pillow_show): Captures `PIL.Image.show()` calls.

> Cillow does not add the prebuilt patches by default. You need to add them explicitly. This provides more flexibility and control if you wish to process those streams in a different way.

---

## Writing Your Own Patches

> Any callable can be patched, whether it is a function, class, or method.

```python
from contextlib import contextmanager
import os

import cillow

os_system_switchable = cillow.Switchable(os.system)

@contextmanager
def patch_os_system():
    def disabled_os_system(command: str):
        return "os.system has been disabled."

    with os_system_switchable.switch_to(disabled_os_system):
        yield
```

```python
with patch_os_system():
    print(os.system("echo hello"))
```

!!! success "Output"
    ```text
    os.system has been disabled.
    ```

It is recommended to avoid fully disabling functionality, as it might be needed elsewhere for actual operations. Instead, modify the functionality based on your specific use case.

For example, if you want to disable functionality only for certain inputs, you can add conditional checks instead of disabling the entire functionality:

```python
os_system_switchable = cillow.Switchable(os.system)

@contextmanager
def patch_os_system():
    def ignore_rm_command(command: str):
        if command.startswith("rm"):
            return "rm commands are blocked."
        return os_system_switchable.original(command)

    with os_system_switchable.switch_to(ignore_rm_command):
        yield
```

!!! tip "Important"
    Avoid directly invoking the patched callable within a patch function, as it can cause an infinite loop.

    Instead, use the `original` method of the `Switchable` instance to access the original functionality.

    **Example**: In the example above, we used `os_system_switchable.original` instead of `os.system` to call the original `os.system` function.

```python
with patch_os_system():
    print(os.system("echo hello"))
    print(os.system("rm -rf /"))
```

!!! success "Output"
    ```text
    hello
    0  # os.system returns 0 for successful execution
    rm commands are blocked.
    ```

> Refer to the [Switchable component](../sdk_reference/switchable.md) to learn how it works internally.

---

### Adding Patches

```python
cillow.add_patches(patch_os_system)
```

---

### Clearing Patches

```python
cillow.clear_patches()
```
