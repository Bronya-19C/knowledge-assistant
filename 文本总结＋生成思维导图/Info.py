import ImageGenerator
from camel.agents import ChatAgent
from camel.configs import SiliconFlowConfig
from camel.models import ModelFactory
from camel.types import ModelPlatformType
import json
class InfoReader:
    def __init__(self,input_message=''):
        self.model = ModelFactory.create(
            model_platform=ModelPlatformType.SILICONFLOW,
            model_type="deepseek-ai/DeepSeek-V3",
            model_config_dict=SiliconFlowConfig(
                stream=True, 
                temperature=0.3,
                max_tokens=2048
            ).as_dict(),
            api_key=pass
        )
        #self.sys_msg = "你是一个文本总结器"
        # self.InfoReader_agent = ChatAgent(
        # system_message=self.sys_msg,
        # model=self.model,
        # output_language="中文"
        # )
        
    def __call__(self,input_message=''):
        self.user_msg = input_message
        # self.response = self.InfoReader_agent.step(self.user_msg)

        # self.info=self.response.msg.content

        #print(response.msg.content)

        self.sys_msg = "你是一个json生成器"

        self.JsonGenerator_agent = ChatAgent(
        system_message=self.sys_msg,
        model=self.model,
        output_language="中文"
        )

        self.additional="""

        你要把这些信息转化一个这样的json格式：
        {
                    "中心主题": {
                        "children": ["分支1", "分支2", "分支3"],
                        "expanded": False,
                        "level": 0
                    },
                    "分支1": {
                        "children": ["子分支1-1", "子分支1-2"],
                        "expanded": False,
                        "level": 1
                    },
                    "分支2": {
                        "children": ["子分支2-1", "子分支2-2"],
                        "expanded": False,
                        "level": 1
                    },
                    "分支3": {
                        "children": [],
                        "expanded": True,
                        "level": 1
                    },
                    "子分支1-1": {
                        "children": [],
                        "expanded": True,
                        "level": 2
                    },
                    "子分支1-2": {
                        "children": [],
                        "expanded": True,
                        "level": 2
                    },
                    "子分支2-1": {
                        "children": [],
                        "expanded": True,
                        "level": 2
                    },
                    "子分支2-2": {
                        "children": [],
                        "expanded": True,
                        "level": 2
                    }
                    ……
        }
                注意：先输出level小的内容，即从浅层到深层
                第0层的key要设定为“知识图谱”
                多总结一些分支内容，要求多于2层的分支，3层最好，要生成最后一层叶子节点，即children为空，不要忘记封闭json格式
                将“中心主题，子分支1”等换为相应内容，在最后一层节点中保留尽可能多的字数，如：- **量子力学规则**：颠覆经典计算的底层原理,这样的，你应该做成两个节点！不要输出多余的话,不要输出三引号和json！！！
                小心不要犯在json文本中缺少引号等低级错误,要检查json格式！！！
        """

        self.json_response=self.JsonGenerator_agent.step(self.user_msg+self.additional)

        self.Real_Json=json.loads(self.json_response.msg.content)

        #print(list(self.Real_Json))

        return self.Real_Json
