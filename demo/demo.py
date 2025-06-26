import sys
import os
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
import networkx as nx
import matplotlib.patches as patches
import matplotlib.font_manager as fm
import platform
import math
import markdown
import threading
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QTextEdit, 
                             QFileDialog, QProgressBar, QSplitter, QFrame,
                             QTabWidget, QGridLayout, QGroupBox, QRadioButton, QFileDialog, QMessageBox)
from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QPixmap, QIcon, QTextCursor
import graphviz

from camel.agents import ChatAgent, TaskPlannerAgent
from camel.configs import SiliconFlowConfig
from camel.models import ModelFactory
from camel.types import ModelPlatformType

from typing import List, Dict, Tuple
from pptx import Presentation
from docx import Document
import time
import json

import learning_assistant
from subagent import create
from Info import InfoReader

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

# --------------------- 思维导图层 ----------------------------
# 设置中文字体
def set_chinese_font():
    system = platform.system()
    if system == "Windows":
        fonts = ['SimHei', 'Microsoft YaHei', 'KaiTi', 'FangSong']
    elif system == "Darwin":
        fonts = ['Heiti TC', 'Arial Unicode MS', 'PingFang SC']
    else:
        fonts = ['DejaVu Sans', 'WenQuanYi Zen Hei', 'Noto Sans CJK SC']

    for font in fonts:
        try:
            plt.rcParams['font.sans-serif'] = [font]
            plt.rcParams['axes.unicode_minus'] = False
            return font
        except:
            continue

    try:
        available_fonts = [f.name for f in fm.fontManager.ttflist]
        chinese_fonts = [f for f in available_fonts if any(keyword in f.lower() for keyword in ['hei', 'kai', 'song', 'fang', 'yuan', 'microsoft', 'simhei', 'simsun'])]
        if chinese_fonts:
            plt.rcParams['font.sans-serif'] = [chinese_fonts[0]]
            plt.rcParams['axes.unicode_minus'] = False
            return chinese_fonts[0]
    except:
        pass

    return None


class InteractiveMindMap(QWidget):
    def __init__(self, data):
        super().__init__()
        font_name = set_chinese_font()

        self.mindmap_data = data
        self.text_size_cache = {}

        self.setup_ui()
        self.draw_mindmap()

    def setup_ui(self):
        # 创建主布局
        main_layout = QVBoxLayout()

        # 创建 matplotlib 图形
        self.fig, self.ax = plt.subplots(figsize=(14, 10), facecolor='#2e2e2e')
        self.ax.set_facecolor('#2e2e2e')

        # 嵌入到 PySide6
        self.canvas = FigureCanvas(self.fig)
        main_layout.addWidget(self.canvas)

        # 绑定点击事件
        self.canvas.mpl_connect('button_press_event', self.on_click)

        # 控制面板
        control_layout = QHBoxLayout()

        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.draw_mindmap)
        control_layout.addWidget(refresh_btn)

        expand_btn = QPushButton("全部展开")
        expand_btn.clicked.connect(self.expand_all)
        control_layout.addWidget(expand_btn)

        collapse_btn = QPushButton("全部收缩")
        collapse_btn.clicked.connect(self.collapse_all)
        control_layout.addWidget(collapse_btn)

        save_btn = QPushButton("保存图片")
        save_btn.clicked.connect(self.save_image)
        control_layout.addWidget(save_btn)

        save_hd_btn = QPushButton("高清保存")
        save_hd_btn.clicked.connect(self.save_hd_image)
        control_layout.addWidget(save_hd_btn)

        main_layout.addLayout(control_layout)

        self.setLayout(main_layout)

    def get_text_size(self, text, fontsize=10):
        """获取文本的实际显示尺寸"""
        cache_key = (text, fontsize)
        if cache_key in self.text_size_cache:
            return self.text_size_cache[cache_key]

        # 创建临时文本对象来测量尺寸
        temp_text = self.ax.text(0, 0, text, fontsize=fontsize, alpha=0)
        renderer = self.fig.canvas.get_renderer()
        bbox = temp_text.get_window_extent(renderer=renderer)

        # 转换为数据坐标
        bbox_data = bbox.transformed(self.ax.transData.inverted())
        width = bbox_data.width
        height = bbox_data.height

        # 删除临时文本
        temp_text.remove()

        # 缓存结果
        self.text_size_cache[cache_key] = (width, height)
        return width, height

    def get_node_size(self, text, level):
        """根据文本长度和层级计算节点大小"""
        # 基础字体大小
        base_fontsize = 12 if level == 0 else (10 if level == 1 else 8)

        # 获取文本尺寸
        try:
            text_width, text_height = self.get_text_size(text, base_fontsize)
        except:
            # 如果无法获取准确尺寸，使用估算
            char_count = len(text)
            text_width = char_count * 0.05
            text_height = 0.08

        # 计算节点尺寸，确保有足够的边距
        padding_factor = 1.8  # 边距因子
        node_width = max(text_width * padding_factor, 0.3)  # 最小宽度
        node_height = max(text_height * padding_factor, 0.2)  # 最小高度

        # 使用椭圆而不是圆形，以更好地适应文本
        return node_width, node_height

    def draw_mindmap(self):
        self.ax.clear()
        self.ax.set_facecolor('#2e2e2e')

        # 清空文本尺寸缓存
        self.text_size_cache.clear()

        # 创建图
        G = nx.DiGraph()
        visible_nodes = self.get_visible_nodes()

        # 添加节点和边
        for node in visible_nodes:
            G.add_node(node)
            if node != "知识图谱":  # 假设根节点名为"知识图谱"
                parent = self.find_parent(node)
                if parent and parent in visible_nodes:
                    G.add_edge(parent, node)

        if not G.nodes():
            return

        # 使用改进的层次布局
        pos = self.improved_hierarchical_layout(G, "知识图谱")

        # 绘制边
        nx.draw_networkx_edges(G, pos, edge_color='white', width=2, alpha=0.7, ax=self.ax)

        # 绘制节点 - 使用椭圆而不是圆形
        node_colors = []
        for node in G.nodes():
            level = self.mindmap_data[node]["level"]
            if level == 0:
                node_colors.append('#ff6b6b')
            elif level == 1:
                node_colors.append('#4ecdc4')
            elif level == 2:
                node_colors.append('#96ceb4')
            else:
                node_colors.append('#feca57')  # 为更深层级添加新颜色

        # 绘制自定义椭圆节点
        for i, node in enumerate(G.nodes()):
            x, y = pos[node]
            level = self.mindmap_data[node]["level"]

            # 获取节点尺寸
            node_width, node_height = self.get_node_size(node, level)

            # 创建椭圆
            ellipse = patches.Ellipse((x, y), node_width, node_height,
                                      facecolor=node_colors[i], alpha=0.9,
                                      edgecolor='white', linewidth=2)
            self.ax.add_patch(ellipse)

        # 绘制标签
        for node in G.nodes():
            x, y = pos[node]
            level = self.mindmap_data[node]["level"]
            fontsize = 12 if level == 0 else (10 if level == 1 else 8)

            self.ax.text(x, y, node, ha='center', va='center',
                         fontsize=fontsize, color='white', weight='bold',
                         wrap=True)

        # 动态调整坐标轴范围
        if pos:
            x_coords = [pos[node][0] for node in pos]
            y_coords = [pos[node][1] for node in pos]

            margin = 1.0
            x_min, x_max = min(x_coords) - margin, max(x_coords) + margin
            y_min, y_max = min(y_coords) - margin, max(y_coords) + margin

            self.ax.set_xlim(x_min, x_max)
            self.ax.set_ylim(y_min, y_max)

        # 保持纵横比
        self.ax.set_aspect('equal', adjustable='box')

        # 添加展开/收缩指示器
        self.draw_expand_indicators(G, pos)

        self.ax.axis('off')
        self.ax.set_title('交互式思维导图 - 点击节点展开/收缩',
                          color='white', fontsize=14, pad=20)

        # 存储位置信息用于点击检测
        self.node_positions = pos

        self.canvas.draw()

    def draw_expand_indicators(self, G, pos):
        """绘制展开/收缩指示器"""
        for node in G.nodes():
            if self.mindmap_data[node]["children"]:
                x, y = pos[node]

                # 根据节点大小调整指示器位置
                node_width, node_height = self.get_node_size(node, self.mindmap_data[node]["level"])
                offset_x = node_width * 0.6
                indicator_radius = min(node_width, node_height) * 0.1

                if self.mindmap_data[node]["expanded"]:
                    # 实心圆表示可收缩（已展开）
                    circle = patches.Circle((x + offset_x, y), indicator_radius,
                                            facecolor='#ff6b6b', edgecolor='white', linewidth=2)
                    self.ax.add_patch(circle)
                    # 添加白色减号
                    line_half_length = indicator_radius * 0.6
                    self.ax.plot([x + offset_x - line_half_length, x + offset_x + line_half_length],
                                 [y, y], color='white', linewidth=2)
                else:
                    # 空心圆表示可展开（已收缩）
                    circle = patches.Circle((x + offset_x, y), indicator_radius,
                                            facecolor='none', edgecolor='#4ecdc4', linewidth=2)
                    self.ax.add_patch(circle)
                    # 添加加号
                    line_half_length = indicator_radius * 0.6
                    self.ax.plot([x + offset_x - line_half_length, x + offset_x + line_half_length],
                                 [y, y], color='#4ecdc4', linewidth=2)
                    self.ax.plot([x + offset_x, x + offset_x],
                                 [y - line_half_length, y + line_half_length], color='#4ecdc4', linewidth=2)

    def improved_hierarchical_layout(self, G, root):
        """改进的层次化布局算法，支持多层级和避免重叠"""
        pos = {}

        # 计算每个节点的层级
        levels = {}
        for node in G.nodes():
            if node in self.mindmap_data:
                levels[node] = self.mindmap_data[node]["level"]
            else:
                levels[node] = 0

        # 按层级分组节点
        level_groups = {}
        for node, level in levels.items():
            if level not in level_groups:
                level_groups[level] = []
            level_groups[level].append(node)

        # 根节点位置
        pos[root] = (0, 0)

        def calculate_subtree_size(node):
            """计算子树的大小（用于分配空间）"""
            if node not in self.mindmap_data or not self.mindmap_data[node]["children"]:
                return 1

            size = 0
            for child in self.mindmap_data[node]["children"]:
                if child in G.nodes():
                    size += calculate_subtree_size(child)
            return max(1, size)

        def position_children_radial(parent, parent_pos, start_angle, angle_range):
            """使用极坐标布局子节点"""
            if parent not in self.mindmap_data:
                return

            children = [child for child in self.mindmap_data[parent]["children"] if child in G.nodes()]
            if not children:
                return

            parent_level = levels[parent]

            # 根据层级确定半径
            if parent_level == 0:
                base_radius = 2.0
            elif parent_level == 1:
                base_radius = 1.5
            else:
                base_radius = 1.0

            # 计算每个子节点的角度范围
            total_subtree_size = sum(calculate_subtree_size(child) for child in children)

            current_angle = start_angle
            for child in children:
                subtree_size = calculate_subtree_size(child)
                child_angle_range = angle_range * (subtree_size / total_subtree_size) if total_subtree_size > 0 else angle_range / len(children)
                child_angle = current_angle + child_angle_range / 2

                # 计算子节点位置
                child_x = parent_pos[0] + base_radius * math.cos(child_angle)
                child_y = parent_pos[1] + base_radius * math.sin(child_angle)

                pos[child] = (child_x, child_y)

                # 递归处理子节点的子节点
                if self.mindmap_data[child]["children"]:
                    position_children_radial(child, (child_x, child_y),
                                             child_angle - child_angle_range / 2,
                                             child_angle_range)

                current_angle += child_angle_range

        def position_children_linear(parent, parent_pos):
            """使用线性布局子节点（备选方案）"""
            if parent not in self.mindmap_data:
                return

            children = [child for child in self.mindmap_data[parent]["children"] if child in G.nodes()]
            if not children:
                return

            parent_level = levels[parent]

            # 根据层级确定基础参数
            if parent_level == 0:
                base_radius = 2.0
                vertical_spacing = 0.8
            elif parent_level == 1:
                base_radius = 1.5
                vertical_spacing = 0.6
            else:
                base_radius = 1.0
                vertical_spacing = 0.4

            # 确定子节点的展开方向
            parent_angle = math.atan2(parent_pos[1], parent_pos[0])

            # 计算子节点位置
            start_y = parent_pos[1] - (len(children) - 1) * vertical_spacing / 2

            for i, child in enumerate(children):
                # 根据父节点位置确定子节点的水平位置
                if parent_pos[0] >= 0:  # 右侧
                    child_x = parent_pos[0] + base_radius
                else:  # 左侧
                    child_x = parent_pos[0] - base_radius

                child_y = start_y + i * vertical_spacing

                pos[child] = (child_x, child_y)

                # 递归处理子节点
                position_children_linear(child, (child_x, child_y))

        # 对根节点的直接子节点使用径向布局
        if root in self.mindmap_data and self.mindmap_data[root]["children"]:
            root_children = [child for child in self.mindmap_data[root]["children"] if child in G.nodes()]
            if root_children:
                angle_per_child = 2 * math.pi / len(root_children)
                for i, child in enumerate(root_children):
                    angle = i * angle_per_child
                    child_x = 2.0 * math.cos(angle)
                    child_y = 2.0 * math.sin(angle)
                    pos[child] = (child_x, child_y)

                    # 为每个主分支分配角度范围
                    branch_angle_range = angle_per_child * 0.8  # 留一些间隙
                    position_children_radial(child, (child_x, child_y),
                                             angle - branch_angle_range / 2,
                                             branch_angle_range)

        # 检查并调整重叠节点
        pos = self.adjust_overlapping_nodes(pos, G)

        return pos

    def adjust_overlapping_nodes(self, pos, G):
        """调整重叠的节点位置"""
        adjusted_pos = pos.copy()
        max_iterations = 50
        min_distance = 0.5

        for iteration in range(max_iterations):
            moved = False

            for node1 in G.nodes():
                for node2 in G.nodes():
                    if node1 >= node2:  # 避免重复比较
                        continue

                    pos1 = adjusted_pos[node1]
                    pos2 = adjusted_pos[node2]

                    # 计算距离
                    dx = pos2[0] - pos1[0]
                    dy = pos2[1] - pos1[1]
                    distance = math.sqrt(dx * dx + dy * dy)

                    if distance < min_distance and distance > 0:
                        # 计算推开的方向
                        push_distance = (min_distance - distance) / 2
                        push_x = (dx / distance) * push_distance
                        push_y = (dy / distance) * push_distance

                        # 移动节点
                        adjusted_pos[node1] = (pos1[0] - push_x, pos1[1] - push_y)
                        adjusted_pos[node2] = (pos2[0] + push_x, pos2[1] + push_y)
                        moved = True

            if not moved:
                break

        return adjusted_pos

    def get_visible_nodes(self):
        """获取当前应该显示的节点"""
        visible = []

        # 找到根节点
        root_node = None
        for node, data in self.mindmap_data.items():
            if data["level"] == 0:
                root_node = node
                break

        if root_node:
            visible.append(root_node)

            def add_children(parent):
                if parent in self.mindmap_data and self.mindmap_data[parent]["expanded"]:
                    for child in self.mindmap_data[parent]["children"]:
                        if child in self.mindmap_data:  # 确保子节点存在于数据中
                            visible.append(child)
                            add_children(child)

            add_children(root_node)

        return visible

    def find_parent(self, node):
        """找到节点的父节点"""
        for parent, data in self.mindmap_data.items():
            if "children" in data and node in data["children"]:
                return parent
        return None

    def on_click(self, event):
        """处理鼠标点击事件"""
        if event.inaxes != self.ax:
            return

        # 查找最近的节点
        min_dist = float('inf')
        clicked_node = None

        for node, (x, y) in self.node_positions.items():
            dist = ((event.xdata - x) ** 2 + (event.ydata - y) ** 2) ** 0.5
            if dist < min_dist and dist < 0.5:  # 调整点击阈值
                min_dist = dist
                clicked_node = node

        if clicked_node and clicked_node in self.mindmap_data and self.mindmap_data[clicked_node]["children"]:
            # 切换展开/收缩状态
            self.mindmap_data[clicked_node]["expanded"] = not self.mindmap_data[clicked_node]["expanded"]
            self.draw_mindmap()

    def save_image(self):
        """保存思维导图为图片"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "保存思维导图",
                "",
                "PNG图片 (*.png);;JPEG图片 (*.jpg);;SVG矢量图 (*.svg);;PDF文件 (*.pdf);;所有文件 (*.*)"
            )

            if file_path:
                _, ext = os.path.splitext(file_path)
                ext = ext.lower()

                self.fig.savefig(file_path,
                                 facecolor='#2e2e2e',
                                 edgecolor='none',
                                 bbox_inches='tight',
                                 dpi=150,
                                 format=ext[1:] if ext else 'png')

                QMessageBox.information(self, "保存成功", f"思维导图已保存到:\n{file_path}")

        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存图片时出错:\n{str(e)}")

    def save_hd_image(self):
        """保存高清思维导图"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "保存高清思维导图",
                "",
                "PNG图片 (*.png);;JPEG图片 (*.jpg);;SVG矢量图 (*.svg);;PDF文件 (*.pdf);;所有文件 (*.*)"
            )

            if file_path:
                _, ext = os.path.splitext(file_path)
                ext = ext.lower()

                # 创建高分辨率图形
                save_fig, save_ax = plt.subplots(figsize=(20, 15), facecolor='#2e2e2e')
                save_ax.set_facecolor('#2e2e2e')

                # 重新绘制思维导图
                self.draw_mindmap_to_axes(save_ax)

                save_fig.savefig(file_path,
                                 facecolor='#2e2e2e',
                                 edgecolor='none',
                                 bbox_inches='tight',
                                 dpi=300,
                                 format=ext[1:] if ext else 'png')

                plt.close(save_fig)

                QMessageBox.information(self, "保存成功", f"高清思维导图已保存到:\n{file_path}")

        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存高清图片时出错:\n{str(e)}")

    def draw_mindmap_to_axes(self, ax):
        """将思维导图绘制到指定的axes上（用于高清保存）"""
        # 这里可以复用主要的绘制逻辑
        # 为了简化，直接调用主绘制方法的核心逻辑
        temp_ax = self.ax
        self.ax = ax
        self.draw_mindmap()
        self.ax = temp_ax

    def expand_all(self):
        """展开所有节点"""
        for node_data in self.mindmap_data.values():
            if node_data["children"]:  # 只有有子节点的才需要展开
                node_data["expanded"] = True
        self.draw_mindmap()

    def collapse_all(self):
        """收缩所有节点"""
        for node, node_data in self.mindmap_data.items():
            if node_data["level"] > 0:  # 不收缩根节点
                node_data["expanded"] = False
        self.draw_mindmap()

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
        self.read_btn.setEnabled(True)
        self.mind_map_btn.setEnabled(True)
        self.forget_btn.setEnabled(True)
        
        if result["type"] == "document":
            content = result["data"]
            html_content = markdown.markdown(content)
            self.text_result.setHtml(html_content)
            self.result_tab.setCurrentIndex(0)
            self.add_chat_message("系统", f"已生成文档，共{len(content.split())}个单词")
        
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