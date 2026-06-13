"""
语音管家 — 命令解析与路由模块
将自然语言语音指令映射到具体操作
"""

import re
from typing import Optional, Callable
from dataclasses import dataclass, field


@dataclass
class Command:
    """命令定义"""
    name: str
    patterns: list[str]          # 匹配模式列表（正则或关键词）
    description: str
    examples: list[str] = field(default_factory=list)
    handler: Optional[Callable] = None


class CommandParser:
    """命令解析器"""

    def __init__(self):
        self.commands: list[Command] = []
        self._register_defaults()

    def _register_defaults(self):
        """注册内置命令"""
        defaults = [
            Command(
                name="open_app",
                patterns=[
                    r"打开\s*(.+)",
                    r"启动\s*(.+)",
                    r"运行\s*(.+)",
                    r"launch\s*(.+)",
                ],
                description="打开应用程序",
                examples=["打开记事本", "启动浏览器", "打开计算器"],
            ),
            Command(
                name="close_app",
                patterns=[
                    r"关闭\s*(.+)",
                    r"退出\s*(.+)",
                    r"结束\s*(.+)",
                ],
                description="关闭应用程序",
                examples=["关闭浏览器", "退出微信"],
            ),
            Command(
                name="volume_control",
                patterns=[
                    r"音量\s*(.+)",
                    r"声音\s*(.+)",
                    r"静音",
                ],
                description="音量控制",
                examples=["音量调大", "声音调到50", "静音"],
            ),
            Command(
                name="system_control",
                patterns=[
                    r"关机",
                    r"重启",
                    r"锁屏",
                    r"休眠",
                    r"注销",
                ],
                description="系统控制",
                examples=["关机", "重启电脑", "锁屏"],
            ),
            Command(
                name="web_search",
                patterns=[
                    r"搜索\s*(.+)",
                    r"帮我查\s*(.+)",
                    r"百度\s*(.+)",
                    r"search\s*(.+)",
                ],
                description="联网搜索",
                examples=["搜索天气", "帮我查最新新闻"],
            ),
            Command(
                name="file_operation",
                patterns=[
                    r"(打开|查找|搜索)\s*文件\s*(.+)",
                    r"(新建|创建)\s*(文件夹|文件)\s*(.+)",
                    r"(删除|移除)\s*(文件|文件夹)\s*(.+)",
                ],
                description="文件操作",
                examples=["打开文件 报告.docx", "新建文件夹 项目"],
            ),
            Command(
                name="time_query",
                patterns=[
                    r"(现在|当前)?(什么)?(时间|几点)",
                    r"今天(星期|周)?几",
                    r"(今天|明天|昨天)(什么|是)?日期",
                ],
                description="时间日期查询",
                examples=["现在几点", "今天星期几"],
            ),
            Command(
                name="weather_query",
                patterns=[
                    r"天气\s*(.+)",
                    r"(今天|明天)?(什么)?天气",
                ],
                description="天气查询",
                examples=["今天天气", "北京天气"],
            ),
            Command(
                name="screenshot",
                patterns=[
                    r"截图",
                    r"截屏",
                    r"屏幕截图",
                ],
                description="屏幕截图",
                examples=["截图"],
            ),
            Command(
                name="help",
                patterns=[
                    r"帮助",
                    r"你能做什么",
                    r"功能列表",
                    r"help",
                ],
                description="显示帮助信息",
                examples=["帮助", "你能做什么"],
            ),
        ]
        self.commands.extend(defaults)

    def parse(self, text: str) -> Optional[tuple[Command, dict]]:
        """
        解析语音输入，返回匹配的命令和提取的参数
        """
        text = text.strip().lower()
        for cmd in self.commands:
            for pattern in cmd.patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    params = self._extract_params(match, cmd.name)
                    return cmd, params
        return None

    def _extract_params(self, match: re.Match, cmd_name: str) -> dict:
        """从正则匹配中提取参数"""
        params = {"raw": match.group(0)}
        groups = match.groups()
        if groups:
            # 取最后一个非空的捕获组作为主要参数
            for g in reversed(groups):
                if g:
                    params["target"] = g.strip()
                    break
        return params

    def get_help(self) -> str:
        """获取帮助信息"""
        lines = ["=" * 50, "  语音管家 — 可用命令", "=" * 50]
        for cmd in self.commands:
            lines.append(f"\n  [{cmd.name}] {cmd.description}")
            if cmd.examples:
                for ex in cmd.examples[:2]:
                    lines.append(f"    例: {ex}")
        return "\n".join(lines)

    def register(self, cmd: Command):
        """注册自定义命令"""
        self.commands.append(cmd)
