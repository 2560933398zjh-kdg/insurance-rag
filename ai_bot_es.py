import os
import json
import hashlib
import warnings
from typing import List
from elasticsearch import Elasticsearch, helpers
from pypdf import PdfReader
from qwen_agent.agents import Assistant
from qwen_agent.gui import WebUI
from qwen_agent.tools.base import BaseTool, register_tool

warnings.filterwarnings("ignore")


# ==================== Elasticsearch 检索工具 ====================
@register_tool('es_retrieval')
class ESRetrievalTool(BaseTool):
    """使用 Elasticsearch 进行文档检索的工具"""

    name = 'es_retrieval'
    description = '从 Elasticsearch 索引的文档中检索与用户查询相关的内容。'
    parameters = [{
        'name': 'query',
        'type': 'string',
        'description': '用户查询的关键词或问题',
        'required': True
    }, {
        'name': 'files',
        'type': 'list',
        'description': '需要检索的文件列表',
        'required': True
    }]

    def __init__(self, cfg: dict = None):
        super().__init__(cfg)
        self.cfg = cfg or {}
        es_config = self.cfg.get('es', {})
        # 修改以下默认值（从 https 改为 http，移除用户认证）
        self.es_host = es_config.get('host', 'http://localhost')  # 改为 http
        self.es_port = es_config.get('port', 9200)
        self.es_user = es_config.get('user', '')  # 改为空字符串
        self.es_password = es_config.get('password', '')  # 改为空字符串
        self.index_name = es_config.get('index_name', 'qwen_agent_rag_index')
        self.chunk_size = es_config.get('chunk_size', 500)
        self.client = None
        self._connect()
        self._create_index_if_not_exists()

    def _connect(self):
        """建立到 Elasticsearch 的连接"""
        try:
            self.client = Elasticsearch(
                f"{self.es_host}:{self.es_port}",
                basic_auth=(self.es_user, self.es_password) if self.es_user else None,
                verify_certs=False,
                request_timeout=30
            )
            if not self.client.ping():
                raise Exception("连接失败")
            print(f"✅ 成功连接到 Elasticsearch: {self.es_host}:{self.es_port}")
        except Exception as e:
            print(f"❌ 无法连接到 Elasticsearch: {e}")
            self.client = None

    def _create_index_if_not_exists(self):
        """如果索引不存在则创建"""
        if not self.client or self.client.indices.exists(index=self.index_name):
            return
        mapping = {
            "properties": {
                "file_name": {"type": "keyword"},
                "file_path": {"type": "keyword"},
                "chunk_id": {"type": "integer"},
                "content": {"type": "text"},
                "content_length": {"type": "integer"},
                "file_hash": {"type": "keyword"}
            }
        }
        self.client.indices.create(index=self.index_name, mappings=mapping)
        print(f"✅ 索引 '{self.index_name}' 创建成功")

    def _get_file_hash(self, file_path: str) -> str:
        """计算文件哈希值"""
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

    def _is_file_indexed(self, file_path: str) -> bool:
        """检查文件是否已被索引"""
        file_hash = self._get_file_hash(file_path)
        query = {"query": {"term": {"file_hash": file_hash}}}
        try:
            response = self.client.count(index=self.index_name, body=query)
            return response['count'] > 0
        except Exception:
            return False

    def _read_file_content(self, file_path: str) -> str:
        """读取文件内容"""
        content = ""
        file_lower = file_path.lower()

        try:
            if file_lower.endswith('.pdf'):
                reader = PdfReader(file_path)
                for page in reader.pages:
                    content += page.extract_text() or ""
            elif file_lower.endswith('.txt') or file_lower.endswith('.md'):
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            elif file_lower.endswith('.docx'):
                try:
                    from docx import Document
                    doc = Document(file_path)
                    for para in doc.paragraphs:
                        content += para.text + "\n"
                except ImportError:
                    print(f"⚠️  需要安装 python-docx 解析 .docx 文件")
        except Exception as e:
            print(f"❌ 读取文件失败: {e}")
        return content

    def _chunk_text(self, text: str) -> List[str]:
        """文本分块"""
        if not text:
            return []
        # 按段落分块
        paragraphs = text.split('\n')
        chunks = []
        current = ""
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(current) + len(para) + 1 <= self.chunk_size:
                current += para + "\n"
            else:
                if current:
                    chunks.append(current.strip())
                current = para + "\n"
        if current:
            chunks.append(current.strip())
        # 如果分块失败，按字符切分
        if not chunks and text:
            chunks = [text[i:i + self.chunk_size] for i in range(0, len(text), self.chunk_size)]
        return chunks

    def _index_files(self, files: list):
        """索引文件到 ES"""
        for file_path in files:
            if not os.path.exists(file_path):
                continue
            if self._is_file_indexed(file_path):
                print(f"⏭️  跳过已索引: {os.path.basename(file_path)}")
                continue
            content = self._read_file_content(file_path)
            if not content:
                continue
            chunks = self._chunk_text(content)
            if not chunks:
                continue
            actions = []
            for i, chunk in enumerate(chunks):
                actions.append({
                    "_index": self.index_name,
                    "_source": {
                        "file_name": os.path.basename(file_path),
                        "file_path": file_path,
                        "chunk_id": i + 1,
                        "content": chunk,
                        "content_length": len(chunk),
                        "file_hash": self._get_file_hash(file_path)
                    }
                })
            if actions:
                helpers.bulk(self.client, actions)
                self.client.indices.refresh(index=self.index_name)
                print(f"✅ 索引完成: {os.path.basename(file_path)} ({len(chunks)} 个块)")

    def call(self, params: str, **kwargs) -> str:
        """执行检索"""
        if not self.client:
            return json.dumps([{'error': 'Elasticsearch 未连接'}], ensure_ascii=False)

        try:
            params = json.loads(params)
            query = params.get('query', '')
            files = params.get('files', [])
        except json.JSONDecodeError:
            return json.dumps([{'error': '参数格式错误'}], ensure_ascii=False)

        if files:
            self._index_files(files)

        if not query:
            return json.dumps([], ensure_ascii=False)

        try:
            response = self.client.search(
                index=self.index_name,
                body={
                    "query": {"match": {"content": query}},
                    "size": 5
                }
            )
            results = []
            for hit in response['hits']['hits']:
                results.append({
                    "source": f"{hit['_source']['file_name']} (块 {hit['_source']['chunk_id']})",
                    "content": hit['_source']['content'],
                    "score": hit['_score']
                })
            return json.dumps(results, ensure_ascii=False)
        except Exception as e:
            return json.dumps([{'error': f'搜索失败: {str(e)}'}], ensure_ascii=False)


# ==================== 主程序 ====================
def init_agent_service():
    """初始化助手服务"""

    llm_cfg = {
        'model': 'qwen-max',
        'model_server': 'dashscope',
        'api_key': os.environ.get('DASHSCOPE_API_KEY', ''),
        'generate_cfg': {'top_p': 0.8}
    }

    system_instruction = '''你是一个专业的雇主责任险知识助手。
你的任务是基于提供的文档准确回答用户关于雇主责任险的问题。
- 如果文档中有相关信息，请引用文档内容给出详细、清晰的回答。
- 如果文档中没有足够信息，请如实告知用户。
- 回答时使用中文，条理清晰。'''

    # 获取文档文件
    file_dir = os.path.join(os.path.dirname(__file__), 'docs')
    files = []
    if os.path.exists(file_dir):
        for file in os.listdir(file_dir):
            file_path = os.path.join(file_dir, file)
            if os.path.isfile(file_path):
                files.append(file_path)

    print(f'📂 知识库文件列表 ({len(files)} 个文件):')
    for f in files:
        print(f'   - {os.path.basename(f)}')

    # 创建智能体
    bot = Assistant(
        llm=llm_cfg,
        system_message=system_instruction,
        function_list=['es_retrieval'],  # 使用 ES 检索工具
        files=files
    )
    return bot


def main():
    """启动 Web 图形界面"""
    try:
        print("🚀 正在启动 AI 助手 Web 界面 (Elasticsearch 后端)...")
        print("=" * 50)

        bot = init_agent_service()

        chatbot_config = {
            'prompt.suggestions': [
                '介绍下雇主责任险',
                '雇主责任险和工伤保险有什么主要区别？',
                '雇主责任险的保障范围包括哪些内容？',
                '哪些情况属于雇主责任险的责任免除范围？'
            ]
        }

        print("✅ 服务初始化完成，正在启动 Web 界面...")
        WebUI(bot, chatbot_config=chatbot_config).run()

    except Exception as e:
        print(f"❌ 启动失败: {e}")
        print("请检查:")
        print("1. 网络连接和 API Key 配置")
        print("2. Elasticsearch 服务是否正常运行")
        print("3. docs 文件夹是否存在且包含文档")


if __name__ == '__main__':
    main()