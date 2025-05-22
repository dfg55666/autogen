"""
代码执行工具模块 - 基于AutoGen 0.5.6的Python代码和命令行执行工具

本模块提供了两个主要工具：
1. execute_python - 执行任意Python代码
2. execute_command - 执行任意命令行命令（CMD/PowerShell）

这些工具不在沙盒环境中运行，因此请谨慎使用。
"""

import os
import sys
import subprocess
import tempfile
import traceback
from typing import Dict, List, Optional, Union, Any, Tuple
from typing_extensions import Annotated
import io
import contextlib
import json
import platform
import time
import atexit
import signal
import threading

# 尝试导入AutoGen相关模块
try:
    from autogen_core.tools import FunctionTool
    from autogen_core import CancellationToken
except ImportError:
    print("警告: 未找到AutoGen模块，工具将无法作为FunctionTool使用")
    # 定义一个空的FunctionTool类，以便代码可以继续运行
    class FunctionTool:
        def __init__(self, func, **kwargs):
            self.func = func
            self.kwargs = kwargs

    class CancellationToken:
        def __init__(self):
            self.cancelled = False

# 全局变量
IS_WINDOWS = platform.system() == "Windows"
DEFAULT_SHELL = "powershell" if IS_WINDOWS else "bash"

# 后台进程管理
_background_processes = {}
_process_counter = 0
_process_lock = threading.Lock()

def _cleanup_processes():
    """在程序退出时清理所有后台进程"""
    for terminal_id, process_info in list(_background_processes.items()):
        try:
            process = process_info["process"]
            if process.poll() is None:  # 如果进程仍在运行
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
        except Exception as e:
            print(f"清理进程 {terminal_id} 时出错: {e}")

# 注册退出时的清理函数
atexit.register(_cleanup_processes)

# 如果在Windows上，处理SIGINT信号
if IS_WINDOWS:
    try:
        signal.signal(signal.SIGINT, lambda sig, frame: _cleanup_processes())
    except:
        pass

def execute_python(
    code: Annotated[str, "要执行的Python代码"],
    use_file: Annotated[bool, "是否将代码写入临时文件执行，适用于较长的代码"] = False,
    timeout: Annotated[int, "执行超时时间（秒），0表示无限制"] = 30,
    show_error_traceback: Annotated[bool, "是否显示详细错误追踪信息"] = True,
    additional_args: Annotated[List[str], "传递给Python解释器的额外参数"] = None,
) -> str:
    """
    执行任意Python代码并返回结果。

    代码将在当前Python解释器环境中执行，可以访问所有已安装的模块。
    执行结果包括标准输出、标准错误和返回值（如果有）。

    参数:
        code: 要执行的Python代码字符串
        use_file: 是否将代码写入临时文件执行，适用于较长的代码
        timeout: 执行超时时间（秒），0表示无限制
        show_error_traceback: 是否显示详细错误追踪信息
        additional_args: 传递给Python解释器的额外参数

    返回:
        执行结果的字符串表示
    """
    if additional_args is None:
        additional_args = []

    result = {
        "stdout": "",
        "stderr": "",
        "return_value": None,
        "error": None,
        "success": True
    }

    try:
        if use_file:
            # 将代码写入临时文件执行
            with tempfile.NamedTemporaryFile(suffix='.py', mode='w', delete=False) as temp_file:
                temp_file_path = temp_file.name
                temp_file.write(code)

            try:
                # 执行临时文件
                cmd = [sys.executable] + additional_args + [temp_file_path]
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

                try:
                    stdout, stderr = process.communicate(timeout=timeout if timeout > 0 else None)
                    result["stdout"] = stdout
                    result["stderr"] = stderr
                    result["return_value"] = process.returncode
                except subprocess.TimeoutExpired:
                    process.kill()
                    result["success"] = False
                    result["error"] = f"执行超时（{timeout}秒）"
            finally:
                # 删除临时文件
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
        else:
            # 直接在当前进程中执行代码
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()

            with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
                try:
                    # 使用exec执行代码，捕获最后一个表达式的值
                    local_vars = {}
                    exec(code, globals(), local_vars)

                    # 检查是否有返回值（最后一行是表达式）
                    lines = code.strip().split('\n')
                    last_line = lines[-1].strip()
                    if last_line and not (last_line.startswith('import ') or
                                         last_line.startswith('from ') or
                                         last_line.startswith('def ') or
                                         last_line.startswith('class ') or
                                         last_line.startswith('#') or
                                         '=' in last_line):
                        # 尝试重新执行最后一行作为表达式并获取其值
                        try:
                            result["return_value"] = eval(last_line, globals(), local_vars)
                        except:
                            pass

                except Exception as e:
                    result["success"] = False
                    if show_error_traceback:
                        result["error"] = traceback.format_exc()
                    else:
                        result["error"] = str(e)

            result["stdout"] = stdout_capture.getvalue()
            result["stderr"] = stderr_capture.getvalue()

    except Exception as e:
        result["success"] = False
        if show_error_traceback:
            result["error"] = traceback.format_exc()
        else:
            result["error"] = str(e)

    # 格式化输出结果
    output = []
    if result["stdout"]:
        output.append("=== 标准输出 ===\n" + result["stdout"])
    if result["stderr"]:
        output.append("=== 标准错误 ===\n" + result["stderr"])
    if result["return_value"] is not None and not use_file:
        output.append("=== 返回值 ===\n" + str(result["return_value"]))
    if not result["success"]:
        output.append("=== 错误 ===\n" + str(result["error"]))

    return "\n\n".join(output) if output else "代码执行成功，无输出。"

def execute_command(
    command: Annotated[str, "要执行的命令行命令"],
    shell: Annotated[str, "使用的shell类型，可选值：cmd, powershell, bash"] = DEFAULT_SHELL,
    working_dir: Annotated[str, "命令执行的工作目录，默认为当前目录"] = None,
    timeout: Annotated[int, "执行超时时间（秒），0表示无限制"] = 30,
    stdin_input: Annotated[str, "通过标准输入传递给命令的文本"] = None,
    env_vars: Annotated[Dict[str, str], "要设置的环境变量"] = None,
) -> str:
    """
    执行任意命令行命令并返回结果。

    命令将在系统的命令行环境中执行，可以访问所有已安装的命令行工具。
    执行结果包括标准输出、标准错误和返回码。

    参数:
        command: 要执行的命令行命令
        shell: 使用的shell类型，可选值：cmd, powershell, bash
        working_dir: 命令执行的工作目录，默认为当前目录
        timeout: 执行超时时间（秒），0表示无限制
        stdin_input: 通过标准输入传递给命令的文本
        env_vars: 要设置的环境变量

    返回:
        执行结果的字符串表示
    """
    result = {
        "stdout": "",
        "stderr": "",
        "returncode": None,
        "error": None,
        "success": True
    }

    # 确定shell和命令
    shell_cmd = None
    shell_args = []

    if IS_WINDOWS:
        if shell.lower() == "cmd":
            shell_cmd = "cmd.exe"
            shell_args = ["/c", command]
        elif shell.lower() == "powershell":
            shell_cmd = "powershell.exe"
            shell_args = ["-Command", command]
        else:
            result["success"] = False
            result["error"] = f"在Windows上不支持的shell类型: {shell}"
            return f"=== 错误 ===\n{result['error']}"
    else:
        if shell.lower() == "bash":
            shell_cmd = "bash"
            shell_args = ["-c", command]
        else:
            result["success"] = False
            result["error"] = f"在当前系统上不支持的shell类型: {shell}"
            return f"=== 错误 ===\n{result['error']}"

    # 准备环境变量
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)

    try:
        # 执行命令
        process = subprocess.Popen(
            [shell_cmd] + shell_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE if stdin_input else None,
            text=True,
            cwd=working_dir,
            env=env
        )

        try:
            stdout, stderr = process.communicate(
                input=stdin_input,
                timeout=timeout if timeout > 0 else None
            )
            result["stdout"] = stdout
            result["stderr"] = stderr
            result["returncode"] = process.returncode
        except subprocess.TimeoutExpired:
            process.kill()
            result["success"] = False
            result["error"] = f"执行超时（{timeout}秒）"

    except Exception as e:
        result["success"] = False
        result["error"] = str(e)

    # 格式化输出结果
    output = []

    # 添加命令执行信息
    output.append(f"=== 执行命令 ===\n{shell_cmd} {' '.join(shell_args)}")

    # 添加执行状态
    if result["success"]:
        status = "成功" if result["returncode"] == 0 else f"完成但返回非零值: {result['returncode']}"
        output.append(f"=== 执行状态 ===\n{status}")
    else:
        output.append(f"=== 执行状态 ===\n失败")

    # 添加返回码
    if result["returncode"] is not None:
        output.append(f"=== 返回码 ===\n{result['returncode']}")

    # 添加标准输出
    if result["stdout"]:
        output.append("=== 标准输出 ===\n" + result["stdout"])
    else:
        output.append("=== 标准输出 ===\n(无输出)")

    # 添加标准错误
    if result["stderr"]:
        output.append("=== 标准错误 ===\n" + result["stderr"])
    else:
        output.append("=== 标准错误 ===\n(无错误输出)")

    # 添加错误信息
    if not result["success"] and result["error"]:
        output.append("=== 错误详情 ===\n" + str(result["error"]))

    return "\n\n".join(output)

def launch_process(
    command: Annotated[str, "要执行的命令行命令"],
    wait: Annotated[bool, "是否等待命令执行完成"] = True,
    max_wait_seconds: Annotated[int, "最大等待时间（秒）"] = 600,
    shell: Annotated[str, "使用的shell类型，可选值：cmd, powershell, bash"] = DEFAULT_SHELL,
    cwd: Annotated[str, "命令执行的工作目录，默认为当前目录"] = None,
    env_vars: Annotated[Dict[str, str], "要设置的环境变量"] = None,
) -> Dict[str, Any]:
    """
    启动一个新进程，可以选择等待或不等待其完成。

    如果wait=True，则等待进程完成并返回结果。
    如果wait=False，则在后台启动进程并立即返回，可以使用其他工具与进程交互。

    参数:
        command: 要执行的命令行命令
        wait: 是否等待命令执行完成
        max_wait_seconds: 最大等待时间（秒），仅在wait=True时有效
        shell: 使用的shell类型，可选值：cmd, powershell, bash
        cwd: 命令执行的工作目录，默认为当前目录
        env_vars: 要设置的环境变量

    返回:
        包含进程信息的字典
    """
    global _process_counter

    # 确定shell和命令
    shell_cmd = None
    shell_args = []

    if IS_WINDOWS:
        if shell.lower() == "cmd":
            shell_cmd = "cmd.exe"
            shell_args = ["/c", command]
        elif shell.lower() == "powershell":
            shell_cmd = "powershell.exe"
            shell_args = ["-Command", command]
        else:
            return {"error": f"在Windows上不支持的shell类型: {shell}"}
    else:
        if shell.lower() == "bash":
            shell_cmd = "bash"
            shell_args = ["-c", command]
        else:
            return {"error": f"在当前系统上不支持的shell类型: {shell}"}

    # 准备环境变量
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)

    try:
        # 启动进程
        process = subprocess.Popen(
            [shell_cmd] + shell_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            text=True,
            cwd=cwd,
            env=env,
            bufsize=1,  # 行缓冲
            universal_newlines=True
        )

        if wait:
            # 等待进程完成
            try:
                stdout, stderr = process.communicate(timeout=max_wait_seconds)
                return {
                    "stdout": stdout,
                    "stderr": stderr,
                    "returncode": process.returncode,
                    "completed": True
                }
            except subprocess.TimeoutExpired:
                # 超时但不终止进程，将其转为后台进程
                with _process_lock:
                    _process_counter += 1
                    terminal_id = _process_counter
                    _background_processes[terminal_id] = {
                        "process": process,
                        "command": command,
                        "start_time": time.time(),
                        "output_buffer": [],
                        "error_buffer": []
                    }

                # 启动线程收集输出
                threading.Thread(
                    target=_collect_process_output,
                    args=(terminal_id, process),
                    daemon=True
                ).start()

                return {
                    "terminal_id": terminal_id,
                    "message": f"执行超时（{max_wait_seconds}秒），进程已转为后台运行，终端ID: {terminal_id}"
                }
        else:
            # 后台运行
            with _process_lock:
                _process_counter += 1
                terminal_id = _process_counter
                _background_processes[terminal_id] = {
                    "process": process,
                    "command": command,
                    "start_time": time.time(),
                    "output_buffer": [],
                    "error_buffer": []
                }

            # 启动线程收集输出
            threading.Thread(
                target=_collect_process_output,
                args=(terminal_id, process),
                daemon=True
            ).start()

            return {
                "terminal_id": terminal_id,
                "message": f"进程已在后台启动，终端ID: {terminal_id}"
            }

    except Exception as e:
        return {"error": str(e)}

def _collect_process_output(terminal_id, process):
    """收集进程的输出并存储在缓冲区中"""
    try:
        for line in process.stdout:
            with _process_lock:
                if terminal_id in _background_processes:
                    _background_processes[terminal_id]["output_buffer"].append(line)
    except:
        pass

    try:
        for line in process.stderr:
            with _process_lock:
                if terminal_id in _background_processes:
                    _background_processes[terminal_id]["error_buffer"].append(line)
    except:
        pass

def read_process(
    terminal_id: Annotated[int, "终端ID"],
    wait: Annotated[bool, "是否等待命令执行完成"] = False,
    max_wait_seconds: Annotated[int, "最大等待时间（秒）"] = 60,
) -> Dict[str, Any]:
    """
    读取进程的输出。

    如果wait=True且进程尚未完成，则等待进程完成后再返回输出。
    如果wait=False或进程已完成，则立即返回当前输出。

    参数:
        terminal_id: 终端ID
        wait: 是否等待命令执行完成
        max_wait_seconds: 最大等待时间（秒），仅在wait=True时有效

    返回:
        包含进程输出的字典
    """
    with _process_lock:
        if terminal_id not in _background_processes:
            return {"error": f"找不到终端ID: {terminal_id}"}

        process_info = _background_processes[terminal_id]
        process = process_info["process"]

    if wait and process.poll() is None:
        # 等待进程完成或超时
        try:
            process.wait(timeout=max_wait_seconds)
        except subprocess.TimeoutExpired:
            pass

    # 获取输出
    with _process_lock:
        if terminal_id not in _background_processes:
            return {"error": f"找不到终端ID: {terminal_id}"}

        process_info = _background_processes[terminal_id]
        output = "".join(process_info["output_buffer"])
        error = "".join(process_info["error_buffer"])

        # 清空缓冲区
        process_info["output_buffer"] = []
        process_info["error_buffer"] = []

    # 检查进程状态
    returncode = process.poll()
    status = "running" if returncode is None else "completed"

    return {
        "stdout": output,
        "stderr": error,
        "returncode": returncode,
        "status": status
    }

def write_process(
    terminal_id: Annotated[int, "终端ID"],
    input_text: Annotated[str, "要写入进程的文本"],
) -> Dict[str, Any]:
    """
    向进程写入输入。

    参数:
        terminal_id: 终端ID
        input_text: 要写入进程的文本

    返回:
        操作结果
    """
    with _process_lock:
        if terminal_id not in _background_processes:
            return {"error": f"找不到终端ID: {terminal_id}"}

        process_info = _background_processes[terminal_id]
        process = process_info["process"]

    if process.poll() is not None:
        return {"error": "进程已结束，无法写入"}

    try:
        process.stdin.write(input_text + "\n")
        process.stdin.flush()
        return {"message": "输入已写入终端"}
    except Exception as e:
        return {"error": f"写入进程时出错: {str(e)}"}

def kill_process(
    terminal_id: Annotated[int, "终端ID"],
) -> Dict[str, Any]:
    """
    终止进程。

    参数:
        terminal_id: 终端ID

    返回:
        操作结果
    """
    with _process_lock:
        if terminal_id not in _background_processes:
            return {"error": f"找不到终端ID: {terminal_id}"}

        process_info = _background_processes[terminal_id]
        process = process_info["process"]

    if process.poll() is not None:
        with _process_lock:
            del _background_processes[terminal_id]
        return {"message": "进程已经结束"}

    try:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()

        with _process_lock:
            del _background_processes[terminal_id]

        return {"message": "进程已终止"}
    except Exception as e:
        return {"error": f"终止进程时出错: {str(e)}"}

def list_processes() -> Dict[str, Any]:
    """
    列出所有已知的终端及其状态。

    返回:
        包含终端信息的字典
    """
    processes = []
    with _process_lock:
        for terminal_id, process_info in list(_background_processes.items()):
            process = process_info["process"]
            status = "running" if process.poll() is None else "completed"
            run_time = time.time() - process_info["start_time"]

            processes.append({
                "terminal_id": terminal_id,
                "command": process_info["command"],
                "status": status,
                "run_time_seconds": int(run_time),
                "returncode": process.poll()
            })

    return {"processes": processes}

# 创建AutoGen工具
try:
    execute_python_tool = FunctionTool(
        func=execute_python,
        name="execute_python",
        description="执行任意Python代码并返回结果"
    )
    execute_command_tool = FunctionTool(
        func=execute_command,
        name="execute_command",
        description="执行任意命令行命令并返回结果"
    )
    launch_process_tool = FunctionTool(
        func=launch_process,
        name="launch-process",
        description="启动一个新进程，可以选择等待或不等待其完成"
    )
    read_process_tool = FunctionTool(
        func=read_process,
        name="read-process",
        description="读取进程的输出"
    )
    write_process_tool = FunctionTool(
        func=write_process,
        name="write-process",
        description="向进程写入输入"
    )
    kill_process_tool = FunctionTool(
        func=kill_process,
        name="kill-process",
        description="终止进程"
    )
    list_processes_tool = FunctionTool(
        func=list_processes,
        name="list-processes",
        description="列出所有已知的终端及其状态"
    )

    # 所有工具列表
    code_executor_tools = [
        execute_python_tool,
        execute_command_tool,
        launch_process_tool,
        read_process_tool,
        write_process_tool,
        kill_process_tool,
        list_processes_tool
    ]
except NameError:
    # 如果FunctionTool未定义，则跳过工具创建
    code_executor_tools = []
    print("警告: 未能创建AutoGen工具，请确保已安装AutoGen 0.5.6")

# 导出所有工具函数和工具列表
__all__ = [
    # 工具函数
    "execute_python",
    "execute_command",
    "launch_process",
    "read_process",
    "write_process",
    "kill_process",
    "list_processes",
    # 工具列表
    "code_executor_tools"
]

if __name__ == "__main__":
    # 简单的测试
    print("=== 测试Python代码执行 ===")
    result = execute_python("print('Hello, World!')\n2 + 2")
    print(result)

    print("\n=== 测试命令行执行 ===")
    result = execute_command("echo Hello, World!")
    print(result)
