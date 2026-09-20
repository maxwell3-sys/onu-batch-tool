# main.py
import os
import sys
import telnetlib
import threading
import time
from datetime import datetime

import paramiko

from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
    QMessageBox,
    QFileDialog,
    QComboBox,
    QGroupBox,
)

from PyQt5.QtCore import (
    pyqtSignal,
    QObject,
    QTimer,
)


# ================= 信号 =================
class SignalManager(QObject):
    log_signal = pyqtSignal(str)
    finish_signal = pyqtSignal(str)


# ================= 主窗口 =================
class MainWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("ONU批量Telnet工具")
        self.resize(1200, 780)

        self.running = False
        # 日志保存目录
        self.log_dir = None

        # 当前日志文件
        self.log_file_path = None
        # 定时任务列表
        self.scheduled_times = []

        self.signal_manager = SignalManager()

        self.signal_manager.log_signal.connect(self.log)
        self.signal_manager.finish_signal.connect(
            self.task_finished
        )

        # 定时器
        self.timer = QTimer()
        self.timer.timeout.connect(
            self.check_schedule
        )
        self.timer.start(1000)

        self.init_ui()
        self.set_theme()

    # ================= UI =================
    def init_ui(self):

        # ================= OLT =================

        self.connect_type = QComboBox()
        self.connect_type.addItems(["Telnet", "SSH"])

        self.connect_type.currentTextChanged.connect(
            self.on_connect_type_changed
        )

        self.olt_ip_input = QLineEdit()

        self.olt_user_input = QLineEdit()

        self.olt_pass_input = QLineEdit()
        self.olt_pass_input.setEchoMode(QLineEdit.Password)

        self.ssh_port_label = QLabel("SSH端口")

        self.ssh_port_input = QLineEdit("22")

        # ================= ONU =================

        self.onu_port_input = QLineEdit("23")

        self.interval_input = QLineEdit("0.5")

        # ================= OLT布局 =================

        olt_layout = QGridLayout()

        row = 0

        olt_layout.addWidget(QLabel("OLT连接方式"), row, 0)
        olt_layout.addWidget(self.connect_type, row, 1)

        row += 1

        olt_layout.addWidget(QLabel("OLT IP"), row, 0)
        olt_layout.addWidget(self.olt_ip_input, row, 1)

        row += 1

        olt_layout.addWidget(QLabel("OLT账号"), row, 0)
        olt_layout.addWidget(self.olt_user_input, row, 1)

        row += 1

        olt_layout.addWidget(QLabel("OLT密码"), row, 0)
        olt_layout.addWidget(self.olt_pass_input, row, 1)

        row += 1

        olt_layout.addWidget(self.ssh_port_label, row, 0)
        olt_layout.addWidget(self.ssh_port_input, row, 1)

        olt_group = QGroupBox("OLT连接配置")
        olt_group.setLayout(olt_layout)

        # ================= ONU布局 =================

        onu_layout = QGridLayout()

        onu_layout.addWidget(QLabel("ONU Telnet端口号"), 0, 0)
        onu_layout.addWidget(self.onu_port_input, 0, 1)

        onu_layout.addWidget(QLabel("发送间隔（秒）"), 1, 0)
        onu_layout.addWidget(self.interval_input, 1, 1)

        onu_group = QGroupBox("ONU配置")
        onu_group.setLayout(onu_layout)

        # ================= ONU IP =================

        self.onu_ip_text = QTextEdit()

        self.onu_ip_text.setPlaceholderText(
            "每行一个ONU IP"
        )

        # ================= 命令 =================

        self.command_text = QTextEdit()
        self.help_button = QPushButton("命令帮助")

        # --- 新增开始 ---
        # 设置按钮固定宽度为 80，高度为 30（你可以根据需要调整数字）
        self.help_button.setFixedWidth(80)
        self.help_button.setFixedHeight(30)
        # --- 新增结束 ---

        self.help_button.clicked.connect(
            self.show_command_help
        )

        self.command_text.setPlaceholderText(
            "每行一条命令\n"
            "特殊命令格式：cmd(ctrl+c)\n"
            "等待3秒：cmd(wait3)\n"
            "点击“命令帮助”查看更多"
        )

        # ================= 定时 =================

        self.schedule_input = QTextEdit()
        self.schedule_input.setMaximumHeight(80)
        self.schedule_input.setPlaceholderText(
            "每行一个时间\n"
            "例如:\n"
            "2026-06-12 23:00:00\n"
            "2026-06-13 01:00:00"
        )

        self.schedule_btn = QPushButton("启用定时")
        self.schedule_btn.clicked.connect(self.start_schedule)

        # --- 新增：清除定时按钮 ---
        self.clear_schedule_btn = QPushButton("清除定时")
        self.clear_schedule_btn.clicked.connect(self.clear_schedule)

        # 1. 创建一个垂直布局来包裹两个按钮
        btn_v_layout = QVBoxLayout()
        btn_v_layout.addWidget(self.schedule_btn)
        btn_v_layout.addWidget(self.clear_schedule_btn)

        # 可选：设置按钮之间的间距，让布局更美观
        btn_v_layout.setSpacing(5)

        # 2. 主水平布局
        schedule_layout = QHBoxLayout()

        schedule_layout.addWidget(QLabel("定时执行时间"))
        schedule_layout.addWidget(self.schedule_input)

        # 3. 将垂直按钮组加入水平布局
        schedule_layout.addLayout(btn_v_layout)
        # ================= 日志 =================

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)

        # ================= 按钮 =================

        self.start_btn = QPushButton("启动")
        self.stop_btn = QPushButton("停止")
        self.clear_btn = QPushButton("清空日志屏幕")

        self.start_btn.clicked.connect(
            self.start_task
        )

        self.stop_btn.clicked.connect(
            self.stop_task
        )

        self.clear_btn.clicked.connect(
            self.log_text.clear
        )

        btn_layout = QHBoxLayout()

        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.clear_btn)

        # ================= 左侧布局 =================

        left_layout = QVBoxLayout()

        left_layout.addWidget(olt_group)
        left_layout.addWidget(onu_group)

        left_widget = QWidget()

        left_widget.setLayout(left_layout)
        left_widget.setMaximumWidth(340)

        # ================= 顶部布局 =================

        top_layout = QHBoxLayout()

        command_layout = QVBoxLayout()

        command_layout.addWidget(self.help_button)

        command_layout.addWidget(self.command_text)

        command_widget = QWidget()

        command_widget.setLayout(command_layout)

        # 1. 左边配置栏
        top_layout.addWidget(left_widget, 1)

        # 2. 中间 ONU IP 输入框
        top_layout.addWidget(self.onu_ip_text, 1)

        # 3. 右边 命令/帮助区
        top_layout.addWidget(command_widget, 1)

        # ================= 主布局 =================

        main_layout = QVBoxLayout()

        main_layout.addLayout(top_layout)

        main_layout.addLayout(schedule_layout)

        main_layout.addLayout(btn_layout)

        main_layout.addWidget(QLabel("实时日志"))

        main_layout.addWidget(self.log_text)

        self.setLayout(main_layout)

        # 默认隐藏SSH端口
        self.on_connect_type_changed()

    # ================= SSH显示 =================
    def on_connect_type_changed(self):

        mode = self.connect_type.currentText()

        if mode == "Telnet":

            self.ssh_port_label.hide()
            self.ssh_port_input.hide()

        else:

            self.ssh_port_label.show()
            self.ssh_port_input.show()

    # ================= 主题 =================
    def set_theme(self):

        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #ff9900;
                font-size: 14px;
            }

            QLineEdit, QTextEdit, QComboBox {
                background-color: #2b2b2b;
                border: 1px solid #ff9900;
                border-radius: 5px;
                padding: 5px;
                color: white;
            }

            QPushButton {
                background-color: #ff9900;
                color: black;
                border: none;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
            }

            QPushButton:hover {
                background-color: #ffb84d;
            }

            QPushButton:pressed {
                background-color: #cc7a00;
            }

            QGroupBox {
                border: 1px solid #ff9900;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)

    # ================= 日志 =================
    def log(self, text):

        current_time = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        log_line = f"[{current_time}] {text}"

        # ===== UI显示 =====

        self.log_text.append(log_line)

        # UI最多保留100行
        max_lines = 100

        document = self.log_text.document()

        while document.blockCount() > max_lines:
            cursor = self.log_text.textCursor()

            cursor.movePosition(cursor.Start)

            cursor.select(cursor.BlockUnderCursor)

            cursor.removeSelectedText()

            cursor.deleteChar()

        scrollbar = self.log_text.verticalScrollBar()

        scrollbar.setValue(
            scrollbar.maximum()
        )

        # ===== 写入日志文件 =====

        if self.log_file_path:

            try:

                with open(
                        self.log_file_path,
                        "a",
                        encoding="utf-8"
                ) as f:

                    f.write(log_line )

            except Exception as e:

                print("日志写入失败:", e)

    # ================= 定时启动 =================

    def start_schedule(self):
        # 选择日志保存目录
        log_dir = QFileDialog.getExistingDirectory(
            self,
            "选择日志保存目录"
        )

        if not log_dir:
            return

        self.log_dir = log_dir
        text = self.schedule_input.toPlainText()

        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

        self.scheduled_times.clear()

        error_list = []

        for line in lines:

            try:

                dt = datetime.strptime(
                    line,
                    "%Y-%m-%d %H:%M:%S"
                )

                if dt <= datetime.now():
                    error_list.append(
                        f"{line} 已过期"
                    )

                    continue

                self.scheduled_times.append(dt)

            except:

                error_list.append(
                    f"{line} 格式错误"
                )

        if self.scheduled_times:

            self.log(
                f"已添加 {len(self.scheduled_times)} 个定时任务"
            )

            for t in self.scheduled_times:
                self.log(
                    f"定时: "
                    f"{t.strftime('%Y-%m-%d %H:%M:%S')}"
                )

        if error_list:
            QMessageBox.warning(
                self,
                "部分任务失败",
                "\n".join(error_list)
            )

    # ================= 清除定时任务 =================
    def clear_schedule(self):
        if not self.scheduled_times:
            self.log("当前没有待执行的定时任务")
            return

        count = len(self.scheduled_times)
        self.scheduled_times.clear()

        # 可选：清空输入框中的时间文本，让用户知道已清除
        self.schedule_input.clear()

        self.log(f"已清除 {count} 个定时任务")

    # ================= 检查定时 =================

    def check_schedule(self):

        if not self.scheduled_times:
            return

        now = datetime.now()

        execute_list = []

        for task_time in self.scheduled_times:

            if now >= task_time:
                execute_list.append(task_time)

        for task_time in execute_list:

            if self.running:
                self.log("任务冲突，当前任务正在运行，跳过本次定时任务")
                self.scheduled_times.remove(task_time)
                continue

            self.log(
                "定时任务开始执行: "
                f"{task_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            self.start_task()

            self.scheduled_times.remove(task_time)

    # ================= 启动 =================
    def start_task(self):

        if self.running:
            return

        # 自动生成日志文件
        if self.log_dir:

            self.log_file_path = os.path.join(
                self.log_dir,
                datetime.now().strftime(
                    "ONU_Log_%Y-%m-%d_%H-%M-%S.txt"
                )
            )

        else:

            # 非定时任务时选择日志文件
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "选择日志保存位置",
                datetime.now().strftime(
                    "ONU_Log_%Y-%m-%d_%H-%M-%S.txt"
                ),
                "Text Files (*.txt)"
            )

            if not file_path:
                return

            self.log_file_path = file_path

        mode = self.connect_type.currentText()

        olt_ip = self.olt_ip_input.text().strip()

        olt_user = self.olt_user_input.text().strip()

        olt_pass = self.olt_pass_input.text().strip()

        ssh_port = self.ssh_port_input.text().strip()

        onu_port = self.onu_port_input.text().strip()

        try:

            interval = float(
                self.interval_input.text().strip()
            )

        except:

            QMessageBox.warning(
                self,
                "提示",
                "发送间隔必须是数字"
            )

            return

        onu_ips = [
            ip.strip()
            for ip in self.onu_ip_text.toPlainText().splitlines()
            if ip.strip()
        ]

        commands = [
            cmd.strip()
            for cmd in self.command_text.toPlainText().splitlines()
            if cmd.strip()
        ]

        if not olt_ip:

            QMessageBox.warning(
                self,
                "提示",
                "请输入OLT IP"
            )

            return

        if not onu_ips:

            QMessageBox.warning(
                self,
                "提示",
                "请输入ONU IP"
            )

            return

        if not commands:

            QMessageBox.warning(
                self,
                "提示",
                "请输入命令"
            )

            return

        self.running = True

        self.start_btn.setEnabled(False)

        self.log(
            f"共检测到 {len(onu_ips)} 个ONU"
        )

        thread = threading.Thread(
            target=self.worker,
            args=(
                mode,
                olt_ip,
                olt_user,
                olt_pass,
                ssh_port,
                onu_port,
                interval,
                onu_ips,
                commands
            ),
            daemon=True
        )

        thread.start()

    # ================= 可中断等待 =================
    def safe_sleep(self, seconds):

        end_time = time.time() + seconds

        while time.time() < end_time:

            if not self.running:
                return False

            time.sleep(0.1)

        return True

    # ================= 停止 =================
    def stop_task(self):

        self.running = False


        self.start_btn.setEnabled(True)

        self.log("用户停止任务")


    # ================= worker =================
    def worker(
        self,
        mode,
        olt_ip,
        olt_user,
        olt_pass,
        ssh_port,
        onu_port,
        interval,
        onu_ips,
        commands
    ):

        try:

            if mode == "Telnet":

                self.telnet_mode(
                    olt_ip,
                    olt_user,
                    olt_pass,
                    onu_port,
                    interval,
                    onu_ips,
                    commands
                )

            else:

                self.ssh_mode(
                    olt_ip,
                    ssh_port,
                    olt_user,
                    olt_pass,
                    onu_port,
                    interval,
                    onu_ips,
                    commands
                )

        except Exception as e:

            self.signal_manager.log_signal.emit(
                f"发生错误: {str(e)}"
            )

        self.signal_manager.finish_signal.emit(
            "任务结束"
        )

    # ================= Telnet模式 =================
    def telnet_mode(
        self,
        olt_ip,
        olt_user,
        olt_pass,
        onu_port,
        interval,
        onu_ips,
        commands
    ):

        self.signal_manager.log_signal.emit(
            f"Telnet连接OLT: {olt_ip}"
        )

        tn = telnetlib.Telnet(
            olt_ip,
            23,
            timeout=10
        )

        if not self.safe_sleep(1):
            return

        output = tn.read_very_eager().decode(
            "utf-8",
            errors="ignore"
        )

        self.signal_manager.log_signal.emit(output)

        tn.write((olt_user + "\n").encode())

        if not self.safe_sleep(1):
            return

        output = tn.read_very_eager().decode(
            "utf-8",
            errors="ignore"
        )

        self.signal_manager.log_signal.emit(output)

        tn.write((olt_pass + "\n").encode())

        if not self.safe_sleep(2):
            return

        output = tn.read_very_eager().decode(
            "utf-8",
            errors="ignore"
        )

        self.signal_manager.log_signal.emit(output)

        self.process_onu_telnet(
            tn,
            onu_port,
            interval,
            onu_ips,
            commands
        )

        tn.close()

    # ================= SSH模式 =================
    def ssh_mode(
        self,
        olt_ip,
        ssh_port,
        olt_user,
        olt_pass,
        onu_port,
        interval,
        onu_ips,
        commands
    ):

        self.signal_manager.log_signal.emit(
            f"SSH连接OLT: {olt_ip}:{ssh_port}"
        )

        ssh = paramiko.SSHClient()

        ssh.set_missing_host_key_policy(
            paramiko.AutoAddPolicy()
        )

        ssh.connect(
            hostname=olt_ip,
            port=int(ssh_port),
            username=olt_user,
            password=olt_pass,
            timeout=10
        )

        channel = ssh.invoke_shell()

        if not self.safe_sleep(2):
            return

        if channel.recv_ready():

            output = channel.recv(65535).decode(
                "utf-8",
                errors="ignore"
            )

            self.signal_manager.log_signal.emit(
                output
            )

        self.process_onu_ssh(
            channel,
            onu_port,
            interval,
            onu_ips,
            commands
        )

        ssh.close()

    # ================= ONU处理 Telnet =================
    def process_onu_telnet(
        self,
        tn,
        onu_port,
        interval,
        onu_ips,
        commands
    ):

        for onu_ip in onu_ips:

            if not self.running:
                break

            self.signal_manager.log_signal.emit(
                f"开始处理ONU: {onu_ip}"
            )

            telnet_cmd = (
                f"telnet {onu_ip} {onu_port}"
            )

            tn.write((telnet_cmd + "\n").encode())

            self.signal_manager.log_signal.emit(
                f">>> {telnet_cmd}"
            )

            if not self.safe_sleep(2):
                return

            output = tn.read_very_eager().decode(
                "utf-8",
                errors="ignore"
            )

            if output:

                self.signal_manager.log_signal.emit(
                    output
                )

            for cmd in commands:

                if not self.running:
                    break

                special = self.parse_special_command(cmd)

                # ================= 特殊命令 =================

                if special:

                    self.signal_manager.log_signal.emit(
                        f">>> {cmd}"
                    )

                    # wait
                    if special["type"] == "wait":

                        if not self.safe_sleep(special["value"]):
                            return

                        continue

                    # 特殊按键
                    elif special["type"] == "key":

                        tn.sock.sendall(
                            special["value"]
                        )

                # ================= 普通命令 =================

                else:

                    tn.write((cmd + "\n").encode())

                    self.signal_manager.log_signal.emit(
                        f">>> {cmd}"
                    )

                if not self.safe_sleep(interval):
                    return

                output = tn.read_very_eager().decode(
                    "utf-8",
                    errors="ignore"
                )

                if output:
                    self.signal_manager.log_signal.emit(
                        output
                    )

                if not self.safe_sleep(interval):
                    return

                output = tn.read_very_eager().decode(
                    "utf-8",
                    errors="ignore"
                )

                if output:

                    self.signal_manager.log_signal.emit(
                        output
                    )

            self.signal_manager.log_signal.emit(
                f"ONU处理完成: {onu_ip}"
            )

    # ================= ONU处理 SSH =================
    def process_onu_ssh(
        self,
        channel,
        onu_port,
        interval,
        onu_ips,
        commands
    ):

        for onu_ip in onu_ips:

            if not self.running:
                break

            self.signal_manager.log_signal.emit(
                f"开始处理ONU: {onu_ip}"
            )

            telnet_cmd = (
                f"telnet {onu_ip} {onu_port}"
            )

            channel.send(telnet_cmd + "\n")

            self.signal_manager.log_signal.emit(
                f">>> {telnet_cmd}"
            )

            if not self.safe_sleep(2):
                return

            if channel.recv_ready():

                output = channel.recv(
                    65535
                ).decode(
                    "utf-8",
                    errors="ignore"
                )

                self.signal_manager.log_signal.emit(
                    output
                )

            for cmd in commands:

                if not self.running:
                    break

                special = self.parse_special_command(cmd)

                # ================= 特殊命令 =================

                if special:

                    self.signal_manager.log_signal.emit(
                        f">>> {cmd}"
                    )

                    # wait
                    if special["type"] == "wait":

                        if not self.safe_sleep(special["value"]):
                            return

                        continue

                    # 特殊按键
                    elif special["type"] == "key":

                        channel.send(
                            special["value"].decode("latin1")
                        )

                # ================= 普通命令 =================

                else:

                    channel.send(cmd + "\n")

                    self.signal_manager.log_signal.emit(
                        f">>> {cmd}"
                    )

                if not self.safe_sleep(interval):
                    return

                if channel.recv_ready():
                    output = channel.recv(
                        65535
                    ).decode(
                        "utf-8",
                        errors="ignore"
                    )

                    self.signal_manager.log_signal.emit(
                        output
                    )
            self.signal_manager.log_signal.emit(
                f"ONU处理完成: {onu_ip}"
            )

    # ================= 命令帮助 =================
    def show_command_help(self):

        help_text = (
            "普通命令：\n"
            "每行一条，会自动回车执行\n"
            "\n"
            "特殊命令格式：\n"
            "cmd(...)\n"
            "\n"
            "支持的特殊命令：\n"
            "\n"
            "Ctrl按键：\n"
            "支持 ctrl+a ~ ctrl+z\n"
            "cmd(ctrl+c)\n"
            "cmd(ctrl+d)\n"
            "cmd(ctrl+k)\n"
            "\n"
            "方向键：\n"
            "cmd(up)\n"
            "cmd(down)\n"
            "cmd(left)\n"
            "cmd(right)\n"
            "\n"
            "其他按键：\n"
            "cmd(tab)\n"
            "cmd(enter)\n"
            "cmd(backspace)\n"
            "cmd(esc)\n"
            "\n"
            "等待x秒：\n"
            "cmd(wait3)\n"
            "cmd(wait0.5)\n"
        )

        QMessageBox.information(
            self,
            "命令帮助",
            help_text
        )

    # ================= 特殊命令解析 =================
    def parse_special_command(self, cmd):

        cmd = cmd.strip().lower()

        # ================= wait =================

        if cmd.startswith("cmd(wait") and cmd.endswith(")"):

            try:

                value = cmd[8:-1].strip()

                if not value:
                    return None

                wait_time = float(value)

                return {
                    "type": "wait",
                    "value": wait_time
                }

            except:

                return None

        # ================= 特殊按键 =================

        special_map = {

            # ctrl+a ~ ctrl+z
            **{
                f"cmd(ctrl+{chr(i)})": bytes([i - 96])
                for i in range(ord('a'), ord('z') + 1)
            },

            # 功能键
            "cmd(tab)": b"\t",
            "cmd(enter)": b"\r",
            "cmd(backspace)": b"\x08",
            "cmd(esc)": b"\x1b",

            # 方向键
            "cmd(up)": b"\x1b[A",
            "cmd(down)": b"\x1b[B",
            "cmd(left)": b"\x1b[D",
            "cmd(right)": b"\x1b[C",
        }

        if cmd in special_map:
            return {
                "type": "key",
                "value": special_map[cmd]
            }

        return None
    # ================= 完成 =================
    def task_finished(self, text):

        self.running = False

        self.start_btn.setEnabled(True)

        self.log(text)


# ================= 主程序 =================
if __name__ == "__main__":

    app = QApplication(sys.argv)

    window = MainWindow()

    window.show()

    sys.exit(app.exec_())
