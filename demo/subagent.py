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
            assistant_role_name="用JSON格式输出的文档架构师",
            user_role_name="一个专业的任务协调员",
            task_prompt="""任务协调员将文档大纲发送给文档架构师，文档架构师将其快速精炼地分解为可独立处理的部分（每个部分要是要用来生成内容的，因此要展示生成的要求、字数和关键点，字数不会很多，一般不超过300字），最后只输出分解，用JSON格式表示，他不会说多余的话。该分解用如下的形式输出：
{
    "section_1": {
        "title": "标题一",
        "requirements": "内容一",
        "length": "字数限制一",
        "key_points": "关键点一",
    },
    "section_2": {
        "title": "标题二",
        "content": "内容二"
        "length": "字数限制二",
        "key_points": "关键点二",
    },
    ...
}
小心不要犯在json文本中缺少引号等低级错误,要检查json格式！！！""",
            assistant_agent_kwargs={"model": decomposer_model},
            user_agent_kwargs={"model": decomposer_model},
            with_task_specify=False,
            task_type=TaskType.AI_SOCIETY
        )

        # 创建生成Agent
        self.generator = RolePlaying(
            assistant_role_name="内容撰写专家",
            user_role_name="文档架构师",
            task_prompt="文档架构师会给出文档若干个独立的部分，内容撰写专家根据要求对各个部分生成相应的文档内容，他只会按照要求回答生成的对应内容，不会多说话",
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
            content=f"请将以下文档大纲分解为独立的章节部分：\n\n{outline}",
            role_type=RoleType.USER,
            meta_dict={}
        )

        # 获取分解结果
        assistant_response, user_response = self.decomposer.step(decomposition_task)

        if assistant_response.terminated:
            print(f"分解过程终止: {assistant_response.info['termination_reasons']}")
            return {}

        decomposition_result = assistant_response.msg.content
        while decomposition_result and decomposition_result[0] != '{':
            decomposition_result = decomposition_result[1:]
        while decomposition_result and decomposition_result[-1] != '}':
            decomposition_result = decomposition_result[:-1]


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

    def generate_section(self, section_id: str, section_spec: dict | str):
        """为指定部分生成内容"""
        if section_id in self.generated_sections:
            print(f"部分 {section_id} 已生成，跳过")
            return self.generated_sections[section_id]

        # 如果section_spec是字符串，则将其视为内容，并创建一个临时字典
        if isinstance(section_spec, str):
            print(f"生成部分: {section_id} - 无标题 (内容为字符串)")
            # 创建临时字典，包含默认标题和内容
            section_spec = {
                'title': f"部分_{section_id}",
                'content': section_spec  # 注意：这里的内容是原始字符串，但在生成时我们需要用它来作为要求吗？
            }
        else:
            # 如果是字典，正常打印标题
            print(f"生成部分: {section_id} - {section_spec.get('title', '无标题')}")

        # 现在section_spec已经确保是字典，我们从中提取信息用于生成任务
        # 但是，有可能字典中没有'title'键，所以使用get
        title = section_spec.get('title', '无标题')
        requirements = section_spec.get('requirements', '无特殊要求')
        length = section_spec.get('length', '约500字')
        key_points = section_spec.get('key_points', [])
        # 注意：如果传入的section_spec中原本就有内容，我们是否需要将其作为上下文？
        # 根据生成任务的设计，我们可能希望将内容要求传递给生成模型
        # 但这里我们只使用标题、要求、长度和关键点

        # 创建生成任务消息
        generation_task = BaseMessage(
            role_name="文档架构师",
            content=(
                f"请为文档的 '{title}' 部分生成内容。\n"
                f"要求:\n{requirements}\n"
                f"长度: {length}\n"
                f"关键点: {', '.join(key_points) if isinstance(key_points, list) else key_points}"
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

        generated_content = generated_content.replace("Solution:", '')
        generated_content = generated_content.replace("Next request.", '')

        # 存储生成结果
        self.generated_sections[section_id] = {
            "title": title,
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
            if isinstance(section_spec,str):
                full_document.append({
                    "section_id": section_id,
                    "title": "None",
                    "content": content
                })
            else:
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
        model_type=ModelType.SILICONFLOW_DEEPSEEK_V3,  # 可选模型：DeepSeek-V3/R1 等
        model_config_dict=SiliconFlowConfig(
            temperature=0.3,  # 控制生成随机性 (0~1)
            # max_tokens=8000,
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

    return document

# if __name__ == '__main__':
#     outline = """
#     ### 量子计算学习提纲  

# #### **1. 量子计算概述**
# - 量子计算的定义及其与经典计算的区别
# """
#     print(create(outline))