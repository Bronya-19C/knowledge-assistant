import sys
import os
import markdown
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QTextEdit, 
                             QFileDialog, QProgressBar, QSplitter,
                             QTabWidget, QGroupBox, QFileDialog)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QTextCursor

from camel.configs import SiliconFlowConfig
from camel.models import ModelFactory
from camel.types import ModelPlatformType

import time

import learning_assistant
from subagent import create
from Info import InfoReader
from Image import InteractiveMindMap

APIKEY = 'sk-qseennfhdprismchczwnkzpohyjmuwgpiaywuclsisgugfvo'

# 初始化dot.exe所在目录
os.environ["PATH"] += os.pathsep + r'D:\study\2025spring\ai basic\bighw\test\Graphviz-13.0.1-win64\bin'

# 初始化硅基流动模型
model = ModelFactory.create(
    model_platform=ModelPlatformType.SILICONFLOW,
    model_type="deepseek-ai/DeepSeek-V3",  # 可选模型：DeepSeek-V3/R1 等
    model_config_dict=SiliconFlowConfig(
        stream=True,      # !!!!!!!!!!!!!!!!!!!!!!!!!
        temperature=0.3,  # 控制生成随机性 (0~1)
        max_tokens=2048   # 最大输出长度
    ).as_dict(),
    api_key=APIKEY  # 替换为你的 API 密钥
)

# --------------------- 模型层：Agent封装 ---------------------
class CamelAIAgent:
    def __init__(self):
        self.loader = learning_assistant.DocumentLoader()
        self.mem = learning_assistant.MemoryStore()
        self.agent = learning_assistant.LearningAgent(api_key=APIKEY)
        self.Reader=InfoReader()
    
    def process_document(self, file_path):
        """解析文档并返回大纲"""
        # 逐个加载文档，记忆知识领域
        for path in file_path:
            print(f"加载文件: {path}")
            text = self.loader.load(path)
            self.mem.add_document(text)
            # 提取并记忆该文档的知识领域
            domains = self.agent.extract_domains(text, self.mem.get_context())
            for d in domains:
                self.mem.add_domain(d)

        # 使用最后一个文档生成提纲
        content = self.mem.data['documents'][-1]
        outline = self.agent.generate_outline(content, self.mem.get_context())
        return outline
    
    def generate(self, outline):
       return create(outline)


# --------------------- 控制层：多线程任务 ---------------------
class ProcessTaskThread(QThread):
    """后台处理任务线程"""
    task_completed = Signal(dict)
    progress_updated = Signal(int)
    error_occurred = Signal(str)
    
    def __init__(self, agent, task_type, file_path=None, user_input=None):
        super().__init__()
        self.agent = agent
        self.task_type = task_type
        self.file_path = file_path
        self.user_input = user_input
        self.is_running = True
    
    def run(self):
        try:
            if self.task_type == "forget":
                self.progress_updated.emit(100)
                self.task_completed.emit({
                    "type": "forget",
                    "data": ''
                })
                return
            
            if not self.file_path:
                self.error_occurred.emit("请先选择文档")
                return
            self.progress_updated.emit(0)
                
            # 1. 解析文档
            outline = self.agent.process_document([self.file_path])
            self.progress_updated.emit(20)
            
            if self.task_type == "read_document":
                doc_result = self.agent.generate(outline)
                self.progress_updated.emit(60)
                # 模拟进度
                for i in range(60, 101, 10):
                    time.sleep(0.1)
                    self.progress_updated.emit(i)
                self.task_completed.emit({
                    "type": "document",
                    "data": doc_result
                })

            elif self.task_type == "mind_map":
                self.progress_updated.emit(60)
                # 2. 生成思维导图
                mindmap_data = self.agent.Reader(input_message=outline)
                self.progress_updated.emit(100)
                
                # if error:
                #     self.error_occurred.emit(error)
                #     return
                
                self.task_completed.emit({
                    "type": "mind_map",
                    "data": mindmap_data
                })
                
        except Exception as e:
            self.error_occurred.emit(f"处理失败：{str(e)}")
    
    def stop(self):
        self.is_running = False


# --------------------- 视图层：主界面 ---------------------
class GUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CAMEL-AI 文档智能处理系统")
        self.setGeometry(100, 100, 1000, 700)
        self.file_path = ''
        
        self.agent = CamelAIAgent()
        self.current_task_thread = None
        # 用于文本动画的定时器
        self.typing_timer = QTimer(self)
        self.typing_timer.timeout.connect(self.update_typing_text)
        self.typing_data = {
            'full_text': '',      # 完整文本
            'current_text': '',   # 当前已显示的文本
            'index': 0,           # 当前字符索引
        }
        self.setup_ui()
    
    def setup_ui(self):
        # 主布局
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        
        # 顶部控制区
        control_group = QGroupBox("任务控制")
        control_layout = QHBoxLayout()
        
        # 文件选择按钮
        self.file_btn = QPushButton("选择文档")
        self.file_btn.clicked.connect(self.select_file)
        self.file_path_label = QLabel("未选择文档")
        self.file_path_label.setMinimumWidth(300)
        self.file_path_label.setStyleSheet("border: 1px solid #ccc; padding: 5px;")
        
        # 任务按钮
        self.read_btn = QPushButton("生成文档")
        self.read_btn.clicked.connect(lambda: self.execute_task("read_document"))
        self.mind_map_btn = QPushButton("生成思维导图")
        self.mind_map_btn.clicked.connect(lambda: self.execute_task("mind_map"))

        # 清楚记忆按钮
        self.forget_btn = QPushButton("清楚记忆")
        self.forget_btn.clicked.connect(lambda: self.execute_task("forget"))
        
        control_layout.addWidget(self.file_btn)
        control_layout.addWidget(self.file_path_label)
        control_layout.addWidget(self.read_btn)
        control_layout.addWidget(self.mind_map_btn)
        control_layout.addWidget(self.forget_btn)
        control_group.setLayout(control_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        
        # 中间分割区：聊天区与结果区
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧：聊天交互区
        chat_group = QGroupBox("系统提示")
        chat_layout = QVBoxLayout()
        
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setStyleSheet("background-color: #f5f5f5;")
        chat_layout.addWidget(self.chat_history)
        chat_group.setLayout(chat_layout)
        
        # 右侧：结果展示区
        result_group = QGroupBox("结果展示")
        result_layout = QVBoxLayout()
        self.result_tab = QTabWidget()
        
        # 文本结果页
        self.text_result = QTextEdit()
        self.text_result.setReadOnly(True)
        self.result_tab.addTab(self.text_result, "文本内容")
        
        # 思维导图页
        self.mind_map_display = InteractiveMindMap({
            "知识图谱": {
                "children": [],
                "expanded": False,
                "level": 0
            }
        })
        self.mind_map_display.setStyleSheet("border: 1px dashed #ccc; padding: 20px;")
        self.result_tab.addTab(self.mind_map_display, "思维导图")
        
        result_layout.addWidget(self.result_tab)
        result_group.setLayout(result_layout)
        
        splitter.addWidget(chat_group)
        splitter.addWidget(result_group)
        splitter.setSizes([300, 700])  # 初始分割比例
        
        # 底部状态栏
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("就绪")
        
        # 组装主布局
        main_layout.addWidget(control_group)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(splitter)
        main_layout.setStretch(2, 1)  # 让分割区占据主要空间
        
        self.setCentralWidget(central_widget)
    
    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择文档", "", "Office文档 (*.pptx *.docx *.txt);;所有文件 (*.*)"
        )
        if file_path:
            self.file_path = file_path
            self.file_path_label.setText(os.path.basename(file_path))
            self.status_bar.showMessage(f"已选择文档: {os.path.basename(file_path)}")
    
    def execute_task(self, task_type):
        if task_type != "forget" and not hasattr(self, 'file_path'):
            self.status_bar.showMessage("请先选择文档")
            return
        
        # 停止当前任务（如果有）
        if self.current_task_thread and self.current_task_thread.isRunning():
            self.current_task_thread.stop()
            self.current_task_thread.wait()
        
        # 启动新任务线程
        self.current_task_thread = ProcessTaskThread(
            self.agent, task_type, self.file_path
        )
        self.current_task_thread.task_completed.connect(self.handle_task_result)
        self.current_task_thread.progress_updated.connect(self.update_progress)
        self.current_task_thread.error_occurred.connect(self.show_error)
        self.current_task_thread.start()
        
        self.status_bar.showMessage(f"正在执行: {task_type}")
        self.read_btn.setEnabled(False)
        self.mind_map_btn.setEnabled(False)
        self.forget_btn.setEnabled(False)
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
    
    def handle_task_result(self, result):
        self.progress_bar.setValue(100)
        
        if result["type"] == "document":
            content = result["data"]
            html_content = markdown.markdown(content)
            self.text_result.setHtml(html_content)
            self.result_tab.setCurrentIndex(0)
            self.add_chat_message("系统", f"已生成文档，共{len(content.split())}个单词")
            # 配置打字机效果参数
            self.typing_data['full_text'] = content
            self.typing_data['current_text'] = ''
            self.typing_data['index'] = 0
            # 启动文本动画
            self.typing_timer.start(50)  # 每50ms显示一个字符
        
        elif result["type"] == "mind_map":
            self.result_tab.removeTab(1)
            self.mind_map_display = InteractiveMindMap(result["data"])
            self.mind_map_display.setStyleSheet("border: 1px dashed #ccc; padding: 20px;")
            self.result_tab.addTab(self.mind_map_display, "思维导图")
            self.result_tab.setCurrentIndex(1)
            self.add_chat_message("系统", "思维导图生成完成")
        
        elif result["type"] == "forget":
            with open("generated_document.md", "w", encoding="utf-8") as f:
                f.write('')
            with open("memory.json", 'w', encoding='utf-8') as g:
                g.write('{"domains": [], "documents": []}')
            html_content = markdown.markdown('')
            self.text_result.setHtml(html_content)
            self.result_tab.removeTab(1)
            self.mind_map_display = InteractiveMindMap({
                "知识图谱": {
                    "children": [],
                    "expanded": False,
                    "level": 0
                }
            })
            self.mind_map_display.setStyleSheet("border: 1px dashed #ccc; padding: 20px;")
            self.result_tab.addTab(self.mind_map_display, "思维导图")
            self.add_chat_message("系统", f"记忆已清除完毕！")

        self.read_btn.setEnabled(True)
        self.mind_map_btn.setEnabled(True)
        self.forget_btn.setEnabled(True)
                
    def update_typing_text(self):
        # 逐字模式
        if self.typing_data['index'] < len(self.typing_data['full_text']):
            self.typing_data['current_text'] += self.typing_data['full_text'][self.typing_data['index']]
            self.typing_data['index'] += 1
            
            # 将当前文本转换为HTML并显示
            html_content = markdown.markdown(self.typing_data['current_text'])
            self.text_result.setHtml(html_content)
            
            # 滚动到底部
            self.text_result.moveCursor(QTextCursor.End)
        else:
            self.typing_timer.stop()  # 完成后停止计时器        
    
    def show_error(self, error_msg):
        self.progress_bar.setValue(0)
        self.read_btn.setEnabled(True)
        self.mind_map_btn.setEnabled(True)
        self.forget_btn.setEnabled(True)
        self.status_bar.showMessage(f"错误: {error_msg}")
        self.add_chat_message("系统", f"操作失败: {error_msg}")
    
    def add_chat_message(self, sender, message):
        time_str = time.strftime("%H:%M:%S", time.localtime())
        prefix = f"[{time_str}] {sender}: "
        cursor = self.chat_history.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(f"<b>{prefix}</b>{message}\n")
        self.chat_history.ensureCursorVisible()

# --------------------- 程序入口 ---------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    # 设置中文字体
    font = app.font()
    font.setFamily("SimHei")
    app.setFont(font)
    
    window = GUI()
    window.show()
    sys.exit(app.exec())