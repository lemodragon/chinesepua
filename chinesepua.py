import io
import random
import re
import time
import threading

import plugins
import requests
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from common.tmp_dir import TmpDir
from playwright.sync_api import sync_playwright
from plugins import *

from .prompts import get_prompt


def read_file(path):
    with open(path, mode="r", encoding="utf-8") as f:
        return f.read()


@plugins.register(
    name="chinesepua",
    desc="A plugin that generates satirical explanation cards for Chinese phrases",
    version="0.5",
    author="BenedictKing",
    desire_priority=90,
)
class ChinesePua(Plugin):
    def __init__(self):
        super().__init__()

        gconf = super().load_config()
        if not gconf:
            curdir = os.path.dirname(__file__)
            tm_path = os.path.join(curdir, "config.json.template")
            json_path = os.path.join(curdir, "config.json")
            if os.path.exists(json_path):
                # 读取config.json配置文件
                gconf = json.loads(read_file(json_path))
                logger.debug(f"[chinesepua] 从config.json读取配置: {gconf}")
            elif os.path.exists(tm_path):
                # 读取config.json.template配置文件
                gconf = json.loads(read_file(tm_path))
                logger.debug(f"[chinesepua] 读取config.json.template读取配置: {gconf}")
        try:
            self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
            self.api_key = gconf.get("api_key")
            self.api_base = gconf.get("api_base")
            self.api_model = gconf.get("api_model")
            self.claude_key = gconf.get("claude_key")
            self.claude_base = gconf.get("claude_base")
            self.claude_model = gconf.get("claude_model", "claude-3-5-sonnet-20240620")
            self.max_tokens = gconf.get("max_tokens", 0)
            self.with_text = gconf.get("with_text", False)
            logger.debug("[chinesepua] inited")
        except Exception as e:
            logger.error(f"[chinesepua] init error: {e}")

    def on_handle_context(self, e_context: EventContext):
        context = e_context["context"]
        logger.debug(f"[chinesepua] 获取到用户输入：{context.content}")
        # 过滤不需要处理的内容类型
        context = e_context["context"]
        if context.type not in [ContextType.TEXT]:
            return

        keyword = None
        prompt = None

        if context.content.startswith(("设计", "名片")):
            match = re.search(r"(设计|名片)(.+)", context.content)
            if match:
                keyword = match.group(2).strip()
                logger.debug(f"[chinesepua] 名片: {keyword}")
                prompt = get_prompt("card_designer")

        if context.content.startswith(("解字", "字典", "字源")):
            match = re.search(r"(解字|字典|字源)(.+)", context.content)
            if match:
                keyword = match.group(2).strip()
                logger.debug(f"[chinesepua] 解字: {keyword}")
                if len(keyword) > 10:
                    _set_reply_text(
                        "输入太长了，简短一些吧", e_context, level=ReplyType.TEXT
                    )
                    return
                prompt = get_prompt("word_explainer")

        if context.content.startswith(("PUA", "pua", "吐槽", "槽点", "解释", "新解")):
            match = re.search(r"(PUA|pua|吐槽|槽点|解释|新解)(.+)", context.content)
            if match:
                keyword = match.group(2).strip()
                logger.debug(f"[chinesepua] 吐槽: {keyword}")
                if "claude" in keyword or "Claude" in keyword:
                    keyword = keyword.replace("claude", "").replace("Claude", "")
                    prompt = get_prompt("chinese_teacher_claude")
                else:
                    prompt = get_prompt("chinese_teacher")
                if len(keyword) > 10:
                    _set_reply_text(
                        "输入太长了，简短一些吧", e_context, level=ReplyType.TEXT
                    )
                    return

        if context.content.startswith(("翻译")):
            match = re.search(r"(翻译)(.+)", context.content)
            if match:
                keyword = match.group(2).strip()
                logger.debug(f"[chinesepua] 翻译: {keyword}")
                prompt = get_prompt("translate_expert")

        if context.content.startswith(("论证", "分析")):
            match = re.search(r"(论证|分析)(.+)", context.content)
            if match:
                keyword = match.group(2).strip()
                logger.debug(f"[chinesepua] 论证: {keyword}")
                prompt = get_prompt("argument_analyser")

        if context.content.startswith(("撕考者", "思考者", "思考", "撕考")):
            match = re.search(r"(撕考者|思考者|思考|撕考)(.+)", context.content)
            if match:
                keyword = match.group(2).strip()
                logger.debug(f"[chinesepua] 思考: {keyword}")
                prompt = get_prompt("thinker")

        if context.content.startswith(("深度思考者", "深度思考", "沉思", "琢磨")):
            match = re.search(r"(深度思考者|深度思考|沉思|琢磨)(.+)", context.content)
            if match:
                keyword = match.group(2).strip()
                logger.debug(f"[chinesepua] 深度思考: {keyword}")
                prompt = get_prompt("deep_thinker")

        if context.content.startswith(("概念", "概念解释")):
            match = re.search(r"(概念|概念解释)(.+)", context.content)
            if match:
                keyword = match.group(2).strip()
                logger.debug(f"[chinesepua] 概念: {keyword}")
                prompt = get_prompt("concept_explainer")

        if context.content.startswith(("哲学家", "哲学")):
            match = re.search(r"(哲学家|哲学)(.+)", context.content)
            if match:
                keyword = match.group(2).strip()
                logger.debug(f"[chinesepua] 哲学家: {keyword}")
                prompt = get_prompt("philosopher")

        if context.content.startswith(("互联网", "web2")):
            match = re.search(r"(互联网|web2)(.+)", context.content)
            if match:
                keyword = match.group(2).strip()
                logger.debug(f"[chinesepua] 互联网: {keyword}")
                prompt = get_prompt("web2_expert")

        if context.content.startswith(("知识", "知识卡")):
            match = re.search(r"(知识|知识卡)(.+)", context.content)
            if match:
                keyword = match.group(2).strip()
                logger.debug(f"[chinesepua] 知识: {keyword}")
                prompt = get_prompt("knowledge_card")

        if context.content.startswith(("单词", "单词卡")):
            match = re.search(r"(单词|单词卡)(.+)", context.content)
            if match:
                keyword = match.group(2).strip()
                logger.debug(f"[chinesepua] 单词: {keyword}")
                prompt = get_prompt("word_card")

        if (
            prompt
            and prompt.force_claude
            and not (self.claude_base and self.claude_key)
        ):
            _set_reply_text(
                "这个功能需要Claude API，请先配置好再使用",
                e_context,
                level=ReplyType.TEXT,
            )
            return

        if keyword:
            try:
                payload = {
                    "model": (
                        self.claude_model if prompt.force_claude else self.api_model
                    ),
                    "messages": [
                        {"role": "system", "content": prompt.content},
                        {"role": "user", "content": keyword},
                    ],
                }
                if self.max_tokens > 0:
                    payload["max_tokens"] = self.max_tokens

                response = requests.post(
                    "%s/chat/completions"
                    % (self.claude_base if prompt.force_claude else self.api_base),
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                text = response.json()["choices"][0]["message"]["content"]
                logger.debug(f"[chinesepua] 回复: {text}")

                html_match = re.search(r"```html(.*?)```", text, re.DOTALL)
                if html_match:
                    html_content = html_match.group(1).strip()
                else:
                    svg_match = re.search(r"<svg.*?</svg>", text, re.DOTALL)
                    if svg_match:
                        svg_content = svg_match.group(0)
                        html_content = (
                            """
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://cdn.jsdelivr.net/npm/noto-sans-sc@37.0.0/all.min.css" rel="stylesheet">
    <title>汉语新解</title>
    <style>
        body, html {
            margin: 0;
            padding: 0;
            height: 100%;
            display: flex;
            justify-content: center;
            align-items: center;
            font-family: 'Noto Sans SC', sans-serif;
        }
        .card {
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
            position: relative;
            display: flex;
            flex-direction: column;
        }
    </style>
</head>
"""
                            + f"""
<body>
    <div class="card">
        {svg_content}
    </div>
</body>
</html>
"""
                        )
                    else:
                        html_content = ""

                if self.with_text:
                    reply_text = re.split("```", text)[-1].strip()
                    if not reply_text:
                        reply_text = re.split("```", text)[0].strip()
                    if not reply_text:
                        reply_text = re.split("</svg>", text)[-1].strip()
                    if not reply_text:
                        reply_text = re.split("<svg", text)[0].strip()
                else:
                    reply_text = "卡片生成中..."

                if html_content:
                    # 创建新线程来处理HTML渲染
                    thread = threading.Thread(
                        target=self.render_html_to_image,
                        args=(html_content, e_context),
                    )
                    thread.start()
                    logger.debug(f"[chinesepua] 卡片正在生成中...")

                    if self.with_text:
                        reply_text += "\n\n卡片正在生成中..."
                elif not self.with_text:
                    reply_text = "生成失败，请检查模型输出结果"
                    _set_reply_text(reply_text, e_context, level=ReplyType.TEXT)
                    return

                _set_reply_text(reply_text, e_context, level=ReplyType.TEXT)

            except Exception as e:
                logger.error(f"[chinesepua] 错误: {e}")
                _set_reply_text(
                    "解释失败，请稍后再试...", e_context, level=ReplyType.TEXT
                )

    def render_html_to_image(self, html_content, e_context):
        try:
            tmp_path = (
                TmpDir().path()
                + f"chinesepua_{int(time.time())}_{random.randint(1000, 9999)}.png"
            )

            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(
                    viewport={"width": 1080, "height": 2560},
                    device_scale_factor=2,
                )
                page.set_content(html_content)

                # 等待.card元素加载完成
                card_element = page.wait_for_selector(".card")

                if card_element:
                    card_element.screenshot(path=tmp_path)
                else:
                    # 如果没有找到.card元素，则截取整个页面
                    page.screenshot(path=tmp_path)

                browser.close()

            # 读取生成的图片文件
            with open(tmp_path, "rb") as image_file:
                img_byte_arr = io.BytesIO(image_file.read())

            _send_img(e_context, img_byte_arr)

        except Exception as e:
            logger.error(f"HTML渲染为图片失败: {e}")
            # 如果转换失败，可以在这里发送一条错误消息
            _send_reply_text(
                "生成卡片失败，请稍后再试。。。", e_context, level=ReplyType.TEXT
            )

    # 帮助文档
    def get_help_text(self, verbose=False, **kwargs):
        short_help = "简略指南：\n"
        short_help += "1. 使用以下命令输入：\n"
        short_help += "   a. 设计 [姓名] [职位] [公司] [联系方式] - 生成社交名片\n"
        short_help += "   b. 名片 [姓名] [职位] [公司] [联系方式] - 生成名片\n"
        short_help += "   c. 吐槽 [词语] - 返回幽默的解释和文字卡片\n"
        short_help += "2. 输入格式：\n"
        short_help += "   a. 解字 [汉字] - 获取汉字解释和字源信息\n"
        short_help += "   b. 翻译 [内容] - 进行翻译\n"
        short_help += "   c. 论证 [内容] - 进行论证分析\n"
        short_help += "   d. 思考 / 撕考 [内容] - 调用撕考者\n"
        short_help += f"3. 可用的命令：哲学家、互联网、知识、单词等\n"
        if not verbose:
            return short_help

        help_text = "详细指南：\n"
        help_text += "1. 输入格式说明：\n"
        help_text += "   a. 吐槽 [词语]，例如 '吐槽 加班' - 返回幽默的新解释和文字卡片\n"
        help_text += "   b. 设计 / 名片 [姓名] [职位] [公司] [联系方式] - 生成社交名片\n"
        help_text += "2. 输入解字 [汉字]，例如 '解字 敏' 获取详细汉字解释和字源信息\n"
        help_text += "3. 输入翻译 [内容] 进行即时翻译\n"
        help_text += "4. 输入论证 [内容] 或分析 [内容] 进行深度分析和论证，例如：分析 抖音对年轻人的影响利大于弊\n"
        help_text += "5. 输入思考 [内容] 或撕考 [内容] 调用撕考者\n"
        help_text += "6. 输入沉思 [内容] 或琢磨 [内容] 触发沉思模式\n"
        help_text += "7. 输入概念 [内容] 或概念解释 [内容] 进行概念解析\n"
        help_text += "8. 输入哲学家 [内容] 或哲学 [内容] 进行哲学思考\n"
        help_text += "9. 输入互联网 [内容] 或web2 [内容] 调用互联网黑话专家\n"
        help_text += "10. 输入知识 [内容] 或知识卡 [内容] 生成知识卡片\n"
        help_text += "11. 输入单词 [内容] 或单词卡 [内容] 生成单词卡片\n"
        help_text += f"示例：设计 张三 法外狂徒 法学教授 普及法律知识 头像URL 和 个人主页URL\n"
        return help_text


def _set_reply_text(
    content: str, e_context: EventContext, level: ReplyType = ReplyType.ERROR
):
    reply = Reply(level, content)
    e_context["reply"] = reply
    e_context.action = EventAction.BREAK_PASS

def _send_reply_text(
    content: str, e_context: EventContext, level: ReplyType = ReplyType.ERROR
):
    reply = Reply(level, content)
    channel = e_context["channel"]
    channel.send(reply, e_context["context"])


def _send_img(e_context: EventContext, content: any):
    reply = Reply(ReplyType.IMAGE, content)
    channel = e_context["channel"]
    channel.send(reply, e_context["context"])
