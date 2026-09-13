import logging
logging.basicConfig(level=logging.WARNING)
logging.getLogger('qwen_agent_logger').setLevel(logging.WARNING)
logging.getLogger('qwen_agent').setLevel(logging.WARNING)
logging.getLogger('dashscope').setLevel(logging.WARNING)
import os
from qwen_agent.agents import Assistant
from qwen_agent.llm.schema import Message


# ==================== 配置 LLM ====================
llm_cfg = {
    'model': 'qwen-max',
    'model_server': 'dashscope',
    'api_key': os.environ.get('DASHSCOPE_API_KEY', ''),  # 从环境变量读取
    'generate_cfg': {'top_p': 0.8}
}

# ==================== 准备 PDF 文件 ====================
pdf_files = [
    '融盛雇主责任保险条款（B款）.pdf',
    '融盛财产一次性伤残补助金保险.pdf',
    '阳光农业相互保险公司 雇主责任保险条款（2019）.pdf'
]

existing_files = []
for f in pdf_files:
    if os.path.exists(f):
        existing_files.append(f)
    else:
        print(f"警告：文件不存在 - {f}")

if not existing_files:
    print("错误：未找到任何 PDF 文件，请将三个 PDF 放在脚本同目录。")
    exit(1)

print(f"已加载 {len(existing_files)} 个 PDF 文件：{existing_files}")

# ==================== 创建智能体 ====================
system_instruction = '''你是一个专业的雇主责任险知识助手。
你的任务是基于提供的文档准确回答用户关于雇主责任险的问题。
- 如果文档中有相关信息，请引用文档内容给出详细、清晰的回答。
- 如果文档中没有足够信息，请如实告知用户。
- 回答时使用中文，条理清晰。'''

bot = Assistant(
    llm=llm_cfg,
    system_message=system_instruction,
    function_list=[],
    files=existing_files
)

# ==================== 交互式问答循环 ====================
print("\n🤖 雇主责任险智能助手已启动！")
print("请输入您的问题（输入 'exit' 或 'quit' 退出）：\n")

messages = []  # 保留聊天历史，实现多轮对话

while True:
    user_input = input("您: ").strip()
    if user_input.lower() in ['exit', 'quit', '退出']:
        print("再见！")
        break
    if not user_input:
        continue

    messages.append(Message('user', user_input))
    print("\n助手: ", end='', flush=True)
    full_response = ""
    for response in bot.run(messages=messages):
        if response and response[0].content:
            new_content = response[0].content[len(full_response):]
            print(new_content, end='', flush=True)
            full_response = response[0].content
    print("\n")
    # 将助手的回复加入聊天历史，以便下一轮可以引用上下文
    messages.append(Message('assistant', full_response))