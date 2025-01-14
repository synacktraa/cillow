import cillow

cillow.add_patches(
    cillow.prebuilt_patches.patch_stdout_stderr_write,
    cillow.prebuilt_patches.patch_matplotlib_pyplot_show,
    cillow.prebuilt_patches.patch_pillow_show,
)

if __name__ == "__main__":
    server = cillow.Server(port=5556, max_interpreters=2, interpreters_per_client=1)
    server.run()
