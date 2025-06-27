# knowledge-assistant

## 环境要求

- 使用conda配置虚拟环境
  
  -- conda create -n agent python=3.10
  
  -- conda activate agent

- 或者使用venv配置虚拟环境
  
  -- 先安装virtualenv，命令行运行`pip install virtualenv`

  -- **在工作目录下**，使用**python3.10**的编译器运行`python -m venv venv`
  
  -- 激活虚拟环境`.\venv\Scripts\activate.bat`

- 在该虚拟环境下，运行
  
  -- pip install camel-ai[all] PySide6 matplotlib markdown networkx python-docx python-pptx 

## 应用本体是整个demo文件夹
