# knowledge-assistant

这是基于python3.10，使用camel-ai的agent，用Pyside6编写GUI制作而成的知识助手。

支持用户传入pptx,word,txt格式的文档，并以md格式或者可交互式的思维导图的形式输出。

# 安装

建议在虚拟环境中运行。

## 1.配置虚拟环境

- 使用conda配置虚拟环境
  
  `conda create -n agent python=3.10`
  
  `conda activate agent`

- 或者使用venv配置虚拟环境
  
  先安装`virtualenv`，即命令行运行`pip install virtualenv`

  **在工作目录下**，使用**python3.10**的编译器运行`python -m venv venv`
  
  激活虚拟环境`.\venv\Scripts\activate.bat`

## 2.安装所需的python库

在该虚拟环境下，运行

`pip install camel-ai camel-ai[all] PySide6 matplotlib markdown networkx python-docx python-pptx`

## 3.下载整个demo文件夹

# 启动方法

1.需要提前**在config.py中输入硅基流动的api_key**

2.然后使用命令行在demo文件夹目录下输入命令：`python demo.py` 即可启动。
