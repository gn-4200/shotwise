"""rclone transport: push pending jobs and inputs to the remote queue, pull finished results back."""
import subprocess


def _rclone(*args):
    subprocess.run(["rclone", *args], check=True)


def push(config):
    q = config.root / config.pipeline.workers.queue_dir
    remote = config.pipeline.workers.remote
    _rclone("copy", str(q / "pending"), f"{remote}/pending")
    _rclone("copy", str(q / "inputs"), f"{remote}/inputs")
    _rclone("copy", str(config.root / "workflows"), f"{remote}/../workflows")


def pull(config):
    q = config.root / config.pipeline.workers.queue_dir
    remote = config.pipeline.workers.remote
    _rclone("copy", f"{remote}/done", str(q / "done"))
    _rclone("sync", f"{remote}/pending", str(q / "pending"))   # jobs the worker claimed disappear locally too
