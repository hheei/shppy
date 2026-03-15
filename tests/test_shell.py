from __future__ import annotations

from pathlib import Path

from shppy.shell import Shell


def test_env_persistence_and_chained_run() -> None:
    with Shell() as sh:
        sh.run("export MY_PROJECT='Gemini-Tool'").run("echo $MY_PROJECT")
        assert sh.ok
        assert sh.out == "Gemini-Tool"


def test_command_sequence_and_working_directory(tmp_path: Path) -> None:
    with Shell() as sh:
        sh.run(f"cd '{tmp_path}' ; pwd")
        assert sh.ok
        assert sh.out == str(tmp_path)


def test_non_blocking_queue_and_accumulated_output() -> None:
    with Shell() as sh:
        sh.run("sleep 1; echo 'Task Done'").run("echo 'Queued Task'")
        output = sh.out
        assert "Task Done" in output
        assert "Queued Task" in output
        assert sh.out == output


def test_new_task_refreshes_read_batch() -> None:
    with Shell() as sh:
        sh.run("echo 'first'")
        assert sh.out == "first"

        sh.run("echo 'Fresh Output'")
        assert sh.out == "Fresh Output"


def test_error_capture() -> None:
    with Shell() as sh:
        sh.run("ls /not/exist/path")
        assert not sh.ok
        assert sh.code != 0
        assert sh.err


def test_code_out_err_ok() -> None:
    with Shell() as sh:
        sh.run("echo 'Hello World'")
        assert sh.code == 0
        assert sh.ok
        assert sh.out == "Hello World"
        assert sh.err == ""
