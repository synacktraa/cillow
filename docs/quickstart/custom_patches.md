This guide will show you how to write custom patches for your own usecases.

By default, Cillow include patches to capture real-time streaming outputs that are generated during code execution so it can be redirected to the client. Currently, the following are available:

- [`patch_stdout_stderr_write`](../sdk_reference/prebuilt_patches.md#patch_stdout_stderr_write): Captures `sys.stdout` and `sys.stderr` writes.
- [`patch_matplotlib_pyplot_show`](../sdk_reference/prebuilt_patches.md#patch_matplotlib_pyplot_show): Captures `matplotlib.pyplot.show()` calls.
- [`patch_pillow_show`](../sdk_reference/prebuilt_patches.md/#patch_pillow_show): Captures `PIL.Image.show()` calls.


## Writing your own patches

> Any callable can patched be it a function, class, or method.

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

It is recommended to not fully disable a functionality as somewhere it might be used to actually perform some action and disabling it will prevent it from working. Instead, just modify the functionality a little based on your usecase.

For example, if you want the functionality to be disabled for certain inputs, you can use some checks instead of disabling the entire functionality.

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
    Do not call the same functionality you're patching directly in the patch function as it will cause an infinite loop.

    Instead, use the `original` method of the Switchable instance to access the original functionality.

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

> Refer [Switchable component](../sdk_reference/switchable.md) to know how it works internally.

### Adding patches

```python
cillow.add_patches(patch_os_system)
```

### Clearing patches

```python
cillow.clear_patches()
```
