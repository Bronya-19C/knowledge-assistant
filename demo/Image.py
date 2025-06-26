import sys
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
import networkx as nx
import matplotlib.patches as patches
import matplotlib.font_manager as fm
import platform
import os
import math
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QMessageBox
from PySide6.QtCore import Qt


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


if __name__ == "__main__":
    # 创建一个更复杂的多层级示例数据
    sample_data = {
        "知识图谱": {
            "children": ["基础语法", "面向对象编程", "标准库", "第三方库", "项目实战"],
            "expanded": True,
            "level": 0
        },
        "基础语法": {
            "children": ["变量与数据类型", "控制流语句", "函数定义", "异常处理"],
            "expanded": False,
            "level": 1
        },
        "变量与数据类型": {
            "children": ["字符串操作", "列表和元组", "字典和集合", "数值运算"],
            "expanded": False,
            "level": 2
        },
        "字符串操作": {
            "children": ["字符串格式化", "正则表达式", "字符编码"],
            "expanded": False,
            "level": 3
        },
        "字符串格式化": {
            "children": ["f-string", "format方法", "百分号格式化"],
            "expanded": False,
            "level": 4
        },
        "面向对象编程": {
            "children": ["类与对象", "继承与多态", "封装与抽象", "设计模式"],
            "expanded": False,
            "level": 1
        },
        "类与对象": {
            "children": ["类的定义", "实例化", "属性和方法"],
            "expanded": False,
            "level": 2
        },
        "标准库": {
            "children": ["os模块", "sys模块", "datetime模块", "json模块"],
            "expanded": False,
            "level": 1
        },
        "第三方库": {
            "children": ["NumPy", "Pandas", "Matplotlib", "Requests"],
            "expanded": False,
            "level": 1
        },
        "项目实战": {
            "children": ["Web开发", "数据分析", "机器学习", "自动化脚本"],
            "expanded": False,
            "level": 1
        },
        "Web开发": {
            "children": [],
            "expanded": False,
            "level": 2
        }
    }

    app = QApplication(sys.argv)
    window = InteractiveMindMap(sample_data)
    window.show()
    sys.exit(app.exec())
