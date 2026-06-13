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
        """注册内置命令（顺序敏感：高优先级在前）"""
        defaults = [
            # === 高危操作，最高优先级匹配 ===
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
            # === 桌面/回收站特定操作 ===
            Command(
                name="desktop_ops",
                patterns=[
                    r"(打开|进入)\s*回收站",
                    r"清空回收站",
                    r"(整理|清理)\s*桌面",
                    r"回到桌面",
                    r"任务栏\s*(.+)",
                ],
                description="桌面与任务栏操作",
                examples=["整理桌面", "打开回收站", "清空回收站"],
            ),
            # === 应用操作 ===
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
                name="window_control",
                patterns=[
                    r"(最小化|最大化|还原|恢复)\s*(所有)?(窗口)?",
                    r"显示桌面",
                    r"切换窗口",
                    r"alt\s*tab",
                    r"任务视图",
                    r"(置顶|取消置顶)\s*(.+)",
                    r"(分屏|平铺|堆叠|层叠)(窗口)?",
                ],
                description="窗口管理",
                examples=["最小化所有窗口", "显示桌面", "切换窗口"],
            ),
            Command(
                name="keyboard_input",
                patterns=[
                    r"(输入|键入|打出|写入)\s*(.+?)(\s+在|\s+到)?$",
                    r"(复制|粘贴|剪切|全选|撤销|重做|保存|刷新)",
                    r"回车",
                    r"按\s*(下)?\s*(\S+)\s*键",
                    r"快捷键\s*(.+)",
                ],
                description="键盘输入与快捷键",
                examples=["输入你好", "粘贴", "全选", "按回车键"],
            ),
            Command(
                name="mouse_control",
                patterns=[
                    r"(单击|双击|右键)(点击)?\s*$",
                    r"鼠标\s*(.+)",
                    r"移动到\s*(.+)",
                ],
                description="鼠标控制",
                examples=["单击", "双击", "右键点击"],
            ),
            Command(
                name="media_control",
                patterns=[
                    r"(播放|暂停|停止)\s*(音乐|视频)?",
                    r"(上一首|下一首|上一条|下一条)",
                    r"快进",
                    r"快退",
                ],
                description="媒体播放控制",
                examples=["暂停", "下一首", "播放音乐"],
            ),
            Command(
                name="screen_brightness",
                patterns=[
                    r"亮度\s*(.+)",
                    r"(调亮|调暗|变亮|变暗)",
                    r"屏幕(亮|暗)",
                ],
                description="屏幕亮度调节",
                examples=["亮度调高", "调亮屏幕"],
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
            Command(
                name="ai_query",
                patterns=[
                    r"(问|问一下|请问|告诉我)\s*(.+)",
                    r"什么是\s*(.+)",
                    r"怎么(样|办|做)\s*(.+)",
                    r"为什么\s*(.+)",
                    r"如何\s*(.+)",
                    r"介绍一下\s*(.+)",
                ],
                description="AI 智能问答",
                examples=["问一下黑洞是什么", "怎么煎牛排", "介绍一下 Python"],
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
