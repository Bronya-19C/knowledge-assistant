from camel.models import ModelFactory
from camel.societies import RolePlaying
from camel.messages import BaseMessage
from camel.types import TaskType, ModelType, RoleType
from camel.types import ModelPlatformType
from camel.configs import SiliconFlowConfig
import re
import json
import time




class DocumentGenerator:
    def __init__(self, decomposer_model, generator_model):
        """
        文档生成系统：分解模型拆分大纲，生成模型创建内容

        参数:
            decomposer_model: 大纲分解模型类型
            generator_model: 内容生成模型类型
        """
        self.decomposer_model = decomposer_model
        self.generator_model = generator_model

        # 创建分解Agent
        self.decomposer = RolePlaying(
            assistant_role_name="文档架构师",
            user_role_name="任务协调员",
            task_prompt="请将文档大纲分解为可独立处理的部分",
            assistant_agent_kwargs={"model": decomposer_model},
            user_agent_kwargs={"model": decomposer_model},
            with_task_specify=False,
            task_type=TaskType.AI_SOCIETY
        )

        # 创建生成Agent
        self.generator = RolePlaying(
            assistant_role_name="内容撰写专家",
            user_role_name="文档架构师",
            task_prompt="请根据要求生成文档内容",
            assistant_agent_kwargs={"model": generator_model},
            user_agent_kwargs={"model": generator_model},
            with_task_specify=False,
            task_type=TaskType.AI_SOCIETY
        )

        # 存储文档结构
        self.document_structure = {}
        self.generated_sections = {}

    def decompose_outline(self, outline: str):
        """将大纲文档分解为多个部分"""
        print("开始分解文档大纲...")

        # 创建分解任务消息
        decomposition_task = BaseMessage(
            role_name="任务协调员",
            content=f"请将以下文档大纲分解为独立的章节部分，输出JSON格式：\n\n{outline}",
            role_type=RoleType.USER,
            meta_dict={}
        )

        # 获取分解结果
        assistant_response, user_response = self.decomposer.step(decomposition_task)

        if assistant_response.terminated:
            print(f"分解过程终止: {assistant_response.info['termination_reasons']}")
            return {}

        decomposition_result = assistant_response.msg.content

        print(f"大纲分解结果:\n{decomposition_result}")

        # 尝试解析JSON格式的分解结果
        try:
            # 尝试直接解析JSON
            sections = json.loads(decomposition_result)
        except json.JSONDecodeError:
            # 如果直接解析失败，尝试提取JSON部分
            json_match = re.search(r'\{.*\}', decomposition_result, re.DOTALL)
            if json_match:
                try:
                    sections = json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    print("无法解析JSON内容，使用原始结果")
                    sections = {"section_1": {"title": "原始内容", "content": decomposition_result}}
            else:
                print("未找到JSON格式内容，使用原始结果")
                sections = {"section_1": {"title": "原始内容", "content": decomposition_result}}

        # 验证并存储文档结构
        if not isinstance(sections, dict):
            print("分解结果格式错误，应为字典，尝试转换")
            sections = {"section_1": {"title": "转换后内容", "content": str(sections)}}

        self.document_structure = sections
        print(f"成功分解为 {len(sections)} 个部分")
        return sections

    def generate_section(self, section_id: str, section_spec: dict):
        """为指定部分生成内容"""
        if section_id in self.generated_sections:
            print(f"部分 {section_id} 已生成，跳过")
            return self.generated_sections[section_id]

        print(f"生成部分: {section_id} - {section_spec.get('title', '无标题')}")

        # 创建生成任务消息
        generation_task = BaseMessage(
            role_name="文档架构师",
            content=(
                f"请为文档的 '{section_spec['title']}' 部分生成内容。\n"
                f"要求:\n{section_spec.get('requirements', '无特殊要求')}\n"
                f"长度: {section_spec.get('length', '约500字')}\n"
                f"关键点: {', '.join(section_spec.get('key_points', []))}"
            ),
            role_type=RoleType.USER,
            meta_dict={}
        )

        # 获取生成结果
        assistant_response, user_response = self.generator.step(generation_task)

        if assistant_response.terminated:
            print(f"内容生成终止: {assistant_response.info['termination_reasons']}")
            generated_content = f"内容生成失败: {assistant_response.info['termination_reasons']}"
        else:
            generated_content = assistant_response.msg.content

        # 存储生成结果
        self.generated_sections[section_id] = {
            "title": section_spec["title"],
            "content": generated_content
        }

        print(f"部分 {section_id} 生成完成 ({len(generated_content)} 字符)")
        return generated_content

    def generate_full_document(self, outline: str):
        """生成完整文档"""
        # 步骤1: 分解大纲
        sections = self.decompose_outline(outline)

        # 步骤2: 按顺序生成各部分内容
        full_document = []
        for section_id, section_spec in sections.items():
            content = self.generate_section(section_id, section_spec)
            full_document.append({
                "section_id": section_id,
                "title": section_spec["title"],
                "content": content
            })
            # 添加延迟避免API速率限制
            time.sleep(1)

        # 步骤3: 组合完整文档
        return self._assemble_document(full_document)

    def _assemble_document(self, sections: list):
        """将各部分组合成完整文档"""
        document = "# 文档生成结果\n\n"
        for section in sections:
            document += f"## {section['title']}\n\n"
            document += f"{section['content']}\n\n"
        return document



def create(outline):
    # 初始化文档生成系统
    model = ModelFactory.create(
        model_platform=ModelPlatformType.SILICONFLOW,
        model_type=ModelType.SILICONFLOW_QWEN2_5_72B_INSTRUCT,  # 可选模型：DeepSeek-V3/R1 等
        model_config_dict=SiliconFlowConfig(
            temperature=0.3,  # 控制生成随机性 (0~1)
            max_tokens=4000,
            stream=True
        ).as_dict(),
        api_key='sk-qseennfhdprismchczwnkzpohyjmuwgpiaywuclsisgugfvo',  # 替换为你的 API 密钥
        url='https://api.siliconflow.cn/v1'
    )


    generator = DocumentGenerator(
        decomposer_model=model,  # 使用GPT-4分解大纲
        generator_model=model  # 使用GPT-4生成内容
    )


    # 生成完整文档
    document = generator.generate_full_document(outline)

    # 保存结果
    with open("generated_document.md", "w", encoding="utf-8") as f:
        f.write(document)

    print("文档生成完成，已保存为 generated_document.md")