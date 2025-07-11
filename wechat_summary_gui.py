from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QLabel, QLineEdit, QSpinBox, QPushButton, 
                              QTextEdit, QComboBox, QMessageBox, QTabWidget, 
                              QScrollArea, QFrame, QStackedWidget, QInputDialog, QDialog, QMenu, QListWidget, QListWidgetItem)
from PySide6.QtCore import Qt, QSettings, Signal, QThread, QTimer
from PySide6.QtGui import QFont, QPalette, QColor, QIcon
import sys
import json
import os
from wechat_summary import get_wechat_messages, send_summary, save_summary
from loguru import logger
import resources

class ModernStyle:
    # 颜色
    BACKGROUND = "#ffffff"
    SECONDARY_BACKGROUND = "#f5f5f7"
    TEXT = "#1d1d1f"
    SECONDARY_TEXT = "#86868b"
    ACCENT = "#0066cc"
    BORDER = "#d2d2d7"
    
    # 字体
    FONT_FAMILY = "-apple-system, BlinkMacSystemFont, Microsoft YaHei, Segoe UI"
    
    @staticmethod
    def setup_widget(widget):
        """设置widget的基本样式"""
        widget.setStyleSheet(f"""
            QMainWindow {{
                background-color: {ModernStyle.BACKGROUND};
            }}
            
            QWidget {{
                background-color: {ModernStyle.BACKGROUND};
                color: {ModernStyle.TEXT};
                font-family: {ModernStyle.FONT_FAMILY};
            }}
            
            QLabel {{
                color: {ModernStyle.TEXT};
                font-size: 12px;
                padding: 0;
                margin: 0;
            }}
            
            QLineEdit, QSpinBox, QComboBox {{
                border: 1px solid {ModernStyle.BORDER};
                border-radius: 3px;
                padding: 3px 8px;
                background: white;
                height: 24px;
                font-size: 12px;
            }}
            
            QPushButton {{
                background-color: {ModernStyle.ACCENT};
                color: white;
                border: none;
                border-radius: 3px;
                padding: 3px 12px;
                height: 24px;
                font-size: 12px;
                min-width: 80px;
            }}
            
            QPushButton:hover {{
                background-color: #0077ed;
            }}
            
            QPushButton#mainButton {{
                height: 32px;
                font-size: 13px;
                font-weight: 500;
            }}
            
            QTextEdit {{
                border: 1px solid {ModernStyle.BORDER};
                border-radius: 3px;
                padding: 8px;
                background: white;
                font-size: 12px;
            }}
            
            QTabWidget::pane {{
                border: none;
                background-color: {ModernStyle.BACKGROUND};
            }}
            
            QTabBar::tab {{
                padding: 6px 16px;
                margin-right: 2px;
                color: {ModernStyle.TEXT};
                border: none;
                background: none;
                font-size: 12px;
            }}
            
            QTabBar::tab:selected {{
                color: {ModernStyle.ACCENT};
                border-bottom: 2px solid {ModernStyle.ACCENT};
            }}
            
            QScrollArea {{
                border: none;
            }}
            
            QFrame#configCard {{
                border: 1px solid {ModernStyle.BORDER};
                border-radius: 3px;
                background: white;
                padding: 12px;
                margin: 4px 0;
            }}
        """)

class SummaryWorker(QThread):
    """异步处理总结的工作线程"""
    finished = Signal(str)  # 成功信号
    error = Signal(str)     # 错误信号
    
    def __init__(self, group_name, hours, service_config, prompt):
        super().__init__()
        self.group_name = group_name
        self.hours = hours
        self.service_config = service_config
        self.prompt = prompt
        
    def run(self):
        try:
            summary = get_wechat_messages(
                self.group_name, 
                self.hours, 
                self.service_config,
                self.prompt
            )
            if summary:
                self.finished.emit(summary)
            else:
                self.error.emit("未获取到消息")
        except Exception as e:
            self.error.emit(str(e))

class AIServiceConfig:
    SERVICES = {}  # 移除默认配置，改为空字典
    
    DEFAULT_SERVICES = {
        'DeepSeek': {
            'base_url': 'https://api.deepseek.com',
            'models': ['deepseek-chat', 'deepseek-reasoner']
        },
        'Kimi': {
            'base_url': 'https://api.moonshot.cn/v1',
            'models': ['moonshot-v1-8k', 'moonshot-v1-32k', 'moonshot-v1-128k']
        },
        'Tongyi': {
            'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
            'models': ['qwen-max', 'qwen-plus', 'qwen-turbo']
        }
    }

class AIConfig:
    def __init__(self):
        # 修改配置文件保存路径
        self.config_dir = "config"
        self.config_file = "ai_config.json"
        self.config_path = os.path.join(self.config_dir, self.config_file)
        
        # 确保配置目录存在
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
            
        # 初始化属性
        self.configs = {}
        self.last_service = ''
        self.last_prompt = '默认提示词'
        self.default_prompt = '''你是一个专业的聊天记录总结员，请根据提供的微信群聊天记录生成一个简明的群聊精华总结，重点包括以下内容： 
1. 重要提醒：提取群聊中提到的任何提醒、禁止事项或重要信息。 
2. 今日热门话题：总结群聊中讨论过的主要话题，包含讨论时间、内容摘要、参与者以及关键建议或观点。 
3. 点评：对每个热门话题提供简短的点评，突出群聊中的实用建议或存在的问题。 
4. 待跟进事项：列出群聊中提到的待办事项或需要跟进的事项。 
5. 其他讨论话题：简要总结其他讨论内容。 
6. 结语：对整体讨论的总结，提到群友间的合作和技术交流。'''
        
        # 确保配置文件存在
        if not os.path.exists(self.config_path):
            # 首次运行时，使用默认服务配置
            self.configs = {
                name: {
                    'api_key': '',
                    'base_url': service['base_url'],
                    'model': service['models'][0]
                }
                for name, service in AIServiceConfig.DEFAULT_SERVICES.items()
            }
            # 同步到 SERVICES
            AIServiceConfig.SERVICES = {
                name: {
                    'base_url': service['base_url'],
                    'models': service['models']
                }
                for name, service in AIServiceConfig.DEFAULT_SERVICES.items()
            }
            self.save_configs()
        else:
            self.load_configs()
        
    def load_configs(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'services' in data:
                        self.configs = data['services']
                        # 重置 SERVICES 并从配置文件加载
                        AIServiceConfig.SERVICES.clear()
                        for service_name, config in self.configs.items():
                            AIServiceConfig.SERVICES[service_name] = {
                                'base_url': config['base_url'],
                                'models': [config['model']]
                            }
                    self.default_prompt = data.get('prompt', self.default_prompt)
                    self.last_service = data.get('last_service', '')
                    self.last_prompt = data.get('last_prompt', '默认提示词')
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            # 如果加载失败，使用默认配置
            self.configs = {}
            AIServiceConfig.SERVICES.clear()
            
    def save_configs(self):
        try:
            data = {
                'services': self.configs,
                'prompt': self.default_prompt,
                'last_service': self.last_service,
                'last_prompt': self.last_prompt  # 保存最后使用的提示词
            }
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            logger.info(f"配置已保存到: {self.config_path}")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            
    def add_config(self, name, config):
        """添加或更新配置"""
        self.configs[name] = config
        # 同时更新 AIServiceConfig.SERVICES
        if name not in AIServiceConfig.SERVICES:
            AIServiceConfig.SERVICES[name] = {
                'base_url': config['base_url'],
                'models': [config['model']]
            }
        self.save_configs()
        
    def remove_config(self, name):
        if name in self.configs:
            del self.configs[name]
            self.save_configs()
            
    def get_config(self, name):
        return self.configs.get(name, {})

class ConfigCard(QFrame):
    def __init__(self, service_name, config, parent=None):
        super().__init__(parent)
        self.service_name = service_name  # 保存服务名称
        self.setObjectName("configCard")
        self.setFrameStyle(QFrame.StyledPanel)
        self.setup_ui(service_name, config)
        
    def setup_ui(self, service_name, config):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # 标题和删除按钮容器
        header_container = QWidget()
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        
        # 标题
        title = QLabel(service_name)
        title.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #1d1d1f;
        """)
        header_layout.addWidget(title)
        
        # 删除按钮
        delete_btn = QPushButton("×")
        delete_btn.setFixedSize(24, 24)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #86868b;
                font-size: 18px;
                font-weight: bold;
                border: none;
                border-radius: 12px;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #f5f5f7;
                color: #ff3b30;
            }
        """)
        delete_btn.clicked.connect(self.delete_service)
        header_layout.addWidget(delete_btn, alignment=Qt.AlignRight)
        
        layout.addWidget(header_container)
        
        # API密钥
        key_container = QWidget()
        key_layout = QVBoxLayout(key_container)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.setSpacing(6)
        
        key_label = QLabel("API Key")
        key_label.setStyleSheet("color: #666666;")
        self.key_input = QLineEdit(config.get('api_key', ''))
        self.key_input.setPlaceholderText("请输入API密钥")
        # 添加文本变化监听
        self.key_input.textChanged.connect(self.auto_save_config)
        
        key_layout.addWidget(key_label)
        key_layout.addWidget(self.key_input)
        layout.addWidget(key_container)
        
        # 模型选择
        model_container = QWidget()
        model_layout = QVBoxLayout(model_container)
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.setSpacing(6)
        
        model_label = QLabel("Model")
        model_label.setStyleSheet("color: #666666;")
        
        model_input_container = QWidget()
        model_input_layout = QHBoxLayout(model_input_container)
        model_input_layout.setContentsMargins(0, 0, 0, 0)
        model_input_layout.setSpacing(8)
        
        self.model_combo = CustomComboBox(self)
        self.model_combo.addItems(AIServiceConfig.SERVICES[service_name]['models'])
        current_model = config.get('model')
        if current_model and current_model in AIServiceConfig.SERVICES[service_name]['models']:
            self.model_combo.setCurrentText(current_model)
        # 添加选择变化监听
        self.model_combo.currentTextChanged.connect(self.auto_save_config)
        
        model_input_layout.addWidget(self.model_combo)
        
        # 添加和删除模型按钮
        add_model_btn = QPushButton("添加")
        add_model_btn.setProperty("type", "secondary")
        add_model_btn.clicked.connect(self.add_model)
        
        del_model_btn = QPushButton("删除")
        del_model_btn.setProperty("type", "secondary")
        del_model_btn.clicked.connect(self.delete_model)
        
        model_input_layout.addWidget(add_model_btn)
        model_input_layout.addWidget(del_model_btn)
        
        model_layout.addWidget(model_label)
        model_layout.addWidget(model_input_container)
        layout.addWidget(model_container)

    def auto_save_config(self):
        """配置更改时自动保存"""
        config = self.get_current_config()
        main_window = self.window()
        if isinstance(main_window, MainWindow):
            main_window.save_service_config(self.service_name, config)

    def save_config(self):
        """保存当前服务的配置"""
        self.auto_save_config()

    def delete_service(self):
        """删除服务配置"""
        reply = QMessageBox.question(
            self, 
            "确认删除", 
            f"确定要删除 {self.service_name} 服务吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            main_window = self.window()
            if isinstance(main_window, MainWindow):
                main_window.delete_service_config(self.service_name)

    def add_model(self):
        """添加新模型"""
        model_name, ok = QInputDialog.getText(
            self,
            "添加模型",
            "请输入新模型名称:",
            QLineEdit.Normal
        )
        
        if ok and model_name:
            if model_name not in AIServiceConfig.SERVICES[self.service_name]['models']:
                AIServiceConfig.SERVICES[self.service_name]['models'].append(model_name)
                self.model_combo.addItem(model_name)
                # 自动选择新添加的模型
                self.model_combo.setCurrentText(model_name)
                # 保存更新
                main_window = self.window()
                if isinstance(main_window, MainWindow):
                    main_window.save_service_config(self.service_name, self.get_current_config())

    def delete_model(self):
        """删除当前选中的模型"""
        current_model = self.model_combo.currentText()
        if not current_model:
            return
        
        if len(AIServiceConfig.SERVICES[self.service_name]['models']) <= 1:
            QMessageBox.warning(self, "警告", "必须保留至少一个模型")
            return
        
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除模型 {current_model} 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            AIServiceConfig.SERVICES[self.service_name]['models'].remove(current_model)
            self.model_combo.removeItem(self.model_combo.currentIndex())
            # 保存更新
            main_window = self.window()
            if isinstance(main_window, MainWindow):
                main_window.save_service_config(self.service_name, self.get_current_config())

    def get_current_config(self):
        """获取当前配置"""
        return {
            'api_key': self.key_input.text(),
            'base_url': AIServiceConfig.SERVICES[self.service_name]['base_url'],
            'model': self.model_combo.currentText()
        }

class AddServiceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("添加新服务")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # 服务名称
        name_layout = QVBoxLayout()
        name_label = QLabel("服务名称:")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("例如: OpenAI")
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)
        
        # API Key
        key_layout = QVBoxLayout()
        key_label = QLabel("API Key:")
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("输入API密钥")
        key_layout.addWidget(key_label)
        key_layout.addWidget(self.key_input)
        layout.addLayout(key_layout)
        
        # Base URL
        url_layout = QVBoxLayout()
        url_label = QLabel("API基础URL:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("例如: https://api.openai.com/v1")
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        layout.addLayout(url_layout)
        
        # 模型名称
        model_layout = QVBoxLayout()
        model_label = QLabel("模型名称:")
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("例如: gpt-3.5-turbo")
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_input)
        layout.addLayout(model_layout)
        
        # 按钮
        button_layout = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.accept)
        save_btn.setDefault(True)
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)
        layout.addLayout(button_layout)
        
    def get_service_data(self):
        return {
            'name': self.name_input.text().strip(),
            'api_key': self.key_input.text().strip(),
            'base_url': self.url_input.text().strip(),
            'model': self.model_input.text().strip()
        }

class PromptManager:
    def __init__(self):
        self.config_dir = "config"
        self.config_file = "prompts.json"
        self.config_path = os.path.join(self.config_dir, self.config_file)
        
        # 确保配置目录存在
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
            
        self.prompts = {}
        self.load_prompts()
        
    def load_prompts(self):
        """加载提示词配置"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.prompts = json.load(f)
            else:
                # 默认提示词
                self.prompts = {
                    "默认提示词": {
                        "content": '''你是一个专业的聊天记录总结员，请根据提供的微信群聊天记录生成一个简明的群聊精华总结，重点包括以下内容： 
1. 重要提醒：提取群聊中提到的任何提醒、禁止事项或重要信息。 
2. 今日热门话题：总结群聊中讨论过的主要话题，包含讨论时间、内容摘要、参与者以及关键建议或观点。 
3. 点评：对每个热门话题提供简短的点评，突出群聊中的实用建议或存在的问题。 
4. 待跟进事项：列出群聊中提到的待办事项或需要跟进的事项。 
5. 其他讨论话题：简要总结其他讨论内容。 
6. 结语：对整体讨论的总结，提到群友间的合作和技术交流。''',
                        "description": "默认的群聊总结提示词"
                    }
                }
                self.save_prompts()
        except Exception as e:
            logger.error(f"加载提示词配置失败: {e}")
            
    def save_prompts(self):
        """保存提示词配置"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.prompts, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"保存提示词配置失败: {e}")
            
    def add_prompt(self, name, content, description=""):
        """添加或更新提示词"""
        self.prompts[name] = {
            "content": content,
            "description": description
        }
        self.save_prompts()
        
    def delete_prompt(self, name):
        """删除提示词"""
        if name in self.prompts:
            del self.prompts[name]
            self.save_prompts()
            
    def get_prompt(self, name):
        """获取提示词内容"""
        return self.prompts.get(name, {}).get("content", "")
        
    def get_all_prompts(self):
        """获取所有提示词"""
        return self.prompts

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ai_config = AIConfig()
        self.worker = None
        self.prompt_manager = PromptManager()
        self.setup_ui()
        ModernStyle.setup_widget(self)
        self.setWindowIcon(QIcon(":main.ico"))  # 设置任务栏图标
        
    def setup_ui(self):
        self.setWindowTitle("微信群聊总结工具")
        self.setMinimumSize(600, 500)  # 减小窗口最小尺寸
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建选项卡
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)
        
        # 主要功能选项卡
        main_tab = self.create_main_tab()
        tab_widget.addTab(main_tab, "群聊总结")
        
        # AI配置选项卡
        ai_config_tab = self.create_ai_config_tab()
        tab_widget.addTab(ai_config_tab, "AI服务配置")
        
        # 提示词配置标签页
        prompt_tab = self.create_prompt_tab()
        tab_widget.addTab(prompt_tab, "提示词配置")
        
    def create_main_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 输入区域容器
        input_container = QWidget()
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(12)
        
        # 群聊名称
        group_widget = QWidget()
        group_layout = QVBoxLayout(group_widget)
        group_layout.setContentsMargins(0, 0, 0, 0)
        group_layout.setSpacing(5)
        group_label = QLabel("群聊名称")
        self.group_name_input = QLineEdit()
        group_layout.addWidget(group_label)
        group_layout.addWidget(self.group_name_input)
        input_layout.addWidget(group_widget, 4)
        
        # 时间选择区域
        time_widget = QWidget()
        time_layout = QVBoxLayout(time_widget)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(5)
        time_label = QLabel("获取时间范围")
        
        time_input_widget = QWidget()
        time_input_layout = QHBoxLayout(time_input_widget)
        time_input_layout.setContentsMargins(0, 0, 0, 0)
        time_input_layout.setSpacing(5)
        
        self.hours_spin = QSpinBox()
        self.hours_spin.setRange(0, 23)
        self.hours_spin.setValue(1)
        self.hours_spin.setSuffix(" 小时")
        
        self.minutes_spin = QSpinBox()
        self.minutes_spin.setRange(0, 59)
        self.minutes_spin.setValue(0)
        self.minutes_spin.setSuffix(" 分钟")
        
        time_input_layout.addWidget(self.hours_spin)
        time_input_layout.addWidget(self.minutes_spin)
        
        time_layout.addWidget(time_label)
        time_layout.addWidget(time_input_widget)
        input_layout.addWidget(time_widget, 2)
        
        # AI服务选择
        service_widget = QWidget()
        service_layout = QVBoxLayout(service_widget)
        service_layout.setContentsMargins(0, 0, 0, 0)
        service_layout.setSpacing(5)
        service_label = QLabel("AI服务")
        self.service_combo = QComboBox()
        self.update_service_combo()  # 更新服务列表
        
        # 设置上次使用的服务
        if hasattr(self.ai_config, 'last_service') and self.ai_config.last_service:
            index = self.service_combo.findText(self.ai_config.last_service)
            if index >= 0:
                self.service_combo.setCurrentIndex(index)
        
        service_layout.addWidget(service_label)
        service_layout.addWidget(self.service_combo)
        input_layout.addWidget(service_widget, 2)
        
        layout.addWidget(input_container)
        
        # 获取消息按钮
        get_msg_btn = QPushButton("获取群聊消息")
        get_msg_btn.setObjectName("mainButton")
        get_msg_btn.clicked.connect(self.get_messages)
        layout.addWidget(get_msg_btn)
        
        # 消息预览和编辑区域
        preview_label = QLabel("消息总结预览")
        layout.addWidget(preview_label)
        
        self.summary_edit = QTextEdit()
        layout.addWidget(self.summary_edit)
        
        # 底部容器
        bottom_container = QWidget()
        bottom_layout = QHBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(8)
        
        # 状态标签
        self.status_label = QLabel()
        self.status_label.setStyleSheet(f"color: {ModernStyle.SECONDARY_TEXT};")
        bottom_layout.addWidget(self.status_label)
        
        # 按钮
        save_btn = QPushButton("保存总结")
        save_btn.setFixedWidth(80)
        save_btn.clicked.connect(self.save_summary)
        
        send_btn = QPushButton("发送到群聊")
        send_btn.setFixedWidth(80)
        send_btn.clicked.connect(self.send_to_group)
        
        bottom_layout.addStretch()  # 添加弹性空间，使按钮靠右对齐
        bottom_layout.addWidget(save_btn)
        bottom_layout.addWidget(send_btn)
        
        layout.addWidget(bottom_container)

        # 创建一个 QLabel 并设置其文本为 HTML 格式，包含一个可点击的链接
        self.about_label = QLabel(
            '<p><a href="https://www.allfather.top">愿代码流畅无阻，愿调试轻松自如</a></p>',
            self
        )
        # self.about_label.setStyleSheet("background: lightblue")
        self.about_label.setAlignment(Qt.AlignBottom | Qt.AlignLeft)
        self.about_label.setOpenExternalLinks(True)  # 允许 QLabel 中的链接被点击跳转
        # 将 QLabel 添加到布局中
        layout.addWidget(self.about_label)
        
        return tab
        
    def create_ai_config_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)  # 保存为实例变量
        self.scroll_layout.setSpacing(12)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        
        # 为每个AI服务创建配置卡片
        for service_name in AIServiceConfig.SERVICES:
            config = self.ai_config.get_config(service_name) or {}
            card = ConfigCard(service_name, config)
            self.scroll_layout.addWidget(card)
            
        self.scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # 添加自定义服务按钮
        add_service_btn = QPushButton("添加新服务")
        add_service_btn.clicked.connect(self.add_custom_service)
        layout.addWidget(add_service_btn)
        
        return tab
        
    def create_prompt_tab(self):
        """创建提示词配置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 提示词列表和编辑区域的水平布局
        content_layout = QHBoxLayout()
        
        # 左侧提示词列表
        list_container = QWidget()
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(8)
        
        # 提示词列表标题和添加按钮
        list_header = QWidget()
        list_header_layout = QHBoxLayout(list_header)
        list_header_layout.setContentsMargins(0, 0, 0, 0)
        
        list_title = QLabel("提示词列表")
        list_title.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
        """)
        
        add_btn = QPushButton("+")
        add_btn.setFixedSize(24, 24)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #0066cc;
                color: white;
                border-radius: 12px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0052a3;
            }
        """)
        add_btn.clicked.connect(self.add_new_prompt)
        
        list_header_layout.addWidget(list_title)
        list_header_layout.addWidget(add_btn)
        list_layout.addWidget(list_header)
        
        # 提示词列表
        self.prompt_list = QListWidget()
        self.prompt_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background: white;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background: #f5f5f7;
                color: #0066cc;
            }
        """)
        self.prompt_list.currentItemChanged.connect(self.on_prompt_selected)
        list_layout.addWidget(self.prompt_list)
        
        # 右侧编辑区域
        edit_container = QWidget()
        edit_layout = QVBoxLayout(edit_container)
        edit_layout.setContentsMargins(0, 0, 0, 0)
        edit_layout.setSpacing(8)
        
        # 提示词名称
        name_label = QLabel("提示词名称")
        self.prompt_name_input = QLineEdit()
        self.prompt_name_input.setPlaceholderText("输入提示词名称")
        
        # 提示词描述
        desc_label = QLabel("描述")
        self.prompt_desc_input = QLineEdit()
        self.prompt_desc_input.setPlaceholderText("输入提示词描述（可选）")
        
        # 提示词内容
        content_label = QLabel("提示词内容")
        self.prompt_content_edit = QTextEdit()
        self.prompt_content_edit.setPlaceholderText("输入提示词内容...")
        
        # 操作按钮
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(8)
        
        delete_btn = QPushButton("删除")
        delete_btn.setProperty("type", "danger")
        delete_btn.clicked.connect(self.delete_current_prompt)
        
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_current_prompt)
        
        button_layout.addWidget(delete_btn)
        button_layout.addStretch()
        button_layout.addWidget(save_btn)
        
        # 添加所有组件到编辑区域
        edit_layout.addWidget(name_label)
        edit_layout.addWidget(self.prompt_name_input)
        edit_layout.addWidget(desc_label)
        edit_layout.addWidget(self.prompt_desc_input)
        edit_layout.addWidget(content_label)
        edit_layout.addWidget(self.prompt_content_edit)
        edit_layout.addWidget(button_container)
        
        # 设置左右布局的比例
        content_layout.addWidget(list_container, 1)
        content_layout.addWidget(edit_container, 2)
        
        layout.addLayout(content_layout)
        
        # 初始化提示词列表
        self.update_prompt_list()
        
        # 选中上次使用的提示词
        if self.ai_config.last_prompt:
            items = self.prompt_list.findItems(self.ai_config.last_prompt, Qt.MatchExactly)
            if items:
                self.prompt_list.setCurrentItem(items[0])
        
        return tab
        
    def update_service_combo(self):
        self.service_combo.clear()
        self.service_combo.addItems(AIServiceConfig.SERVICES.keys())
        
    def save_service_config(self, service_name, config):
        """保存服务配置并更新UI"""
        self.ai_config.add_config(service_name, config)
        # 更新服务选择下拉框
        current_service = self.service_combo.currentText()
        self.update_service_combo()
        self.service_combo.setCurrentText(current_service)
        # 更新状态标签而不是弹窗
        if hasattr(self, 'status_label') and self.status_label:
            self.status_label.setText(f"{service_name} 配置已保存")
            # 2秒后清除状态消息
            QTimer.singleShot(2000, lambda: self.status_label.setText(""))
        
    def add_custom_service(self):
        """添加自定义AI服务"""
        dialog = AddServiceDialog(self)
        if dialog.exec():
            data = dialog.get_service_data()
            
            if not all([data['name'], data['api_key'], data['base_url'], data['model']]):
                QMessageBox.warning(self, "警告", "所有字段都必须填写")
                return
                
            # 添加到配置文件
            self.ai_config.add_config(data['name'], {
                'api_key': data['api_key'],
                'base_url': data['base_url'],
                'model': data['model']
            })
            
            # 更新UI
            self.update_service_combo()
            self.update_config_cards()
            
            # 选中新添加的服务
            index = self.service_combo.findText(data['name'])
            if index >= 0:
                self.service_combo.setCurrentIndex(index)
            
            if hasattr(self, 'status_label') and self.status_label:
                self.status_label.setText(f"已添加新服务: {data['name']}")
                QTimer.singleShot(2000, lambda: self.status_label.setText(""))

    def update_config_cards(self):
        """更新配置卡片显示"""
        # 清除现有卡片
        for i in reversed(range(self.scroll_layout.count())):
            widget = self.scroll_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # 重新添加配置卡片
        for service_name in AIServiceConfig.SERVICES:
            config = self.ai_config.get_config(service_name) or {}
            card = ConfigCard(service_name, config)
            self.scroll_layout.addWidget(card)
        
        self.scroll_layout.addStretch()
        
    def update_prompt_list(self):
        """更新提示词列表"""
        self.prompt_list.clear()
        for name in self.prompt_manager.get_all_prompts():
            item = QListWidgetItem(name)
            self.prompt_list.addItem(item)

    def on_prompt_selected(self, current, previous):
        """处理提示词选择变化"""
        if current:
            name = current.text()
            prompt_data = self.prompt_manager.prompts[name]
            self.prompt_name_input.setText(name)
            self.prompt_desc_input.setText(prompt_data.get("description", ""))
            self.prompt_content_edit.setText(prompt_data["content"])
            
            # 保存当前选择的提示词
            self.ai_config.last_prompt = name
            self.ai_config.save_configs()

    def add_new_prompt(self):
        """添加新提示词"""
        name, ok = QInputDialog.getText(
            self,
            "添加提示词",
            "请输入提示词名称:",
            QLineEdit.Normal
        )
        
        if ok and name:
            if name in self.prompt_manager.prompts:
                QMessageBox.warning(self, "警告", "提示词名称已存在")
                return
            
            self.prompt_manager.add_prompt(name, "", "")
            self.update_prompt_list()
            
            # 选中新添加的提示词
            items = self.prompt_list.findItems(name, Qt.MatchExactly)
            if items:
                self.prompt_list.setCurrentItem(items[0])

    def save_current_prompt(self):
        """保存当前提示词"""
        name = self.prompt_name_input.text()
        content = self.prompt_content_edit.toPlainText()
        description = self.prompt_desc_input.text()
        
        if not name:
            QMessageBox.warning(self, "警告", "请输入提示词名称")
            return
        
        if not content:
            QMessageBox.warning(self, "警告", "请输入提示词内容")
            return
        
        # 检查是否修改了名称
        current_item = self.prompt_list.currentItem()
        old_name = current_item.text() if current_item else None
        
        if old_name and old_name != name:
            # 如果修改了名称，需要删除旧的提示词
            self.prompt_manager.delete_prompt(old_name)
        
        self.prompt_manager.add_prompt(name, content, description)
        self.update_prompt_list()
        
        # 选中保存的提示词
        items = self.prompt_list.findItems(name, Qt.MatchExactly)
        if items:
            self.prompt_list.setCurrentItem(items[0])
        
        if hasattr(self, 'status_label') and self.status_label:
            self.status_label.setText("提示词已保存")
            QTimer.singleShot(2000, lambda: self.status_label.setText(""))

    def delete_current_prompt(self):
        """删除当前提示词"""
        current_item = self.prompt_list.currentItem()
        if not current_item:
            return
        
        name = current_item.text()
        if name == "默认提示词":
            QMessageBox.warning(self, "警告", "不能删除默认提示词")
            return
        
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除提示词 {name} 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.prompt_manager.delete_prompt(name)
            self.update_prompt_list()
            
            # 清空编辑区域
            self.prompt_name_input.clear()
            self.prompt_desc_input.clear()
            self.prompt_content_edit.clear()

    def get_messages(self):
        """异步获取消息总结"""
        # 检查是否有配置的AI服务
        if not AIServiceConfig.SERVICES:
            QMessageBox.warning(self, "警告", "请先添加并配置AI服务")
            # 自动切换到AI服务配置标签
            for i in range(self.tab_widget.count()):
                if self.tab_widget.tabText(i) == "AI服务配置":
                    self.tab_widget.setCurrentIndex(i)
                    break
            return
            
        group_name = self.group_name_input.text()
        hours = self.hours_spin.value()
        minutes = self.minutes_spin.value()
        service_name = self.service_combo.currentText()
        
        if not group_name:
            QMessageBox.warning(self, "警告", "请输入群聊名称")
            return
            
        if hours == 0 and minutes == 0:
            QMessageBox.warning(self, "警告", "请设置时间范围")
            return
            
        service_config = self.ai_config.get_config(service_name)
        if not service_config or not service_config.get('api_key'):
            QMessageBox.warning(self, "警告", f"请先配置 {service_name} 的API密钥")
            return
            
        # 保存最后使用的服务和提示词
        self.ai_config.last_service = service_name
        current_item = self.prompt_list.currentItem()
        if current_item:
            self.ai_config.last_prompt = current_item.text()
        self.ai_config.save_configs()
        
        try:
            # 禁用按钮，显示状态
            if hasattr(self, 'status_label') and self.status_label:
                self.status_label.setText("正在生成总结，请稍候...")
            self.setEnabled(False)
            
            # 创建并启动工作线程
            total_minutes = hours * 60 + minutes
            self.worker = SummaryWorker(
                group_name, 
                total_minutes / 60,  # 转换为小时
                service_config,
                self.prompt_content_edit.toPlainText()
            )
            self.worker.finished.connect(self.on_summary_finished)
            self.worker.error.connect(self.on_summary_error)
            self.worker.start()
        except Exception as e:
            self.setEnabled(True)
            if hasattr(self, 'status_label') and self.status_label:
                self.status_label.setText("")
            QMessageBox.critical(self, "错误", f"处理失败: {str(e)}")
        
    def on_summary_finished(self, summary):
        """处理总结完成"""
        self.summary_edit.setText(summary)
        self.status_label.setText("")
        self.setEnabled(True)
        
    def on_summary_error(self, error):
        """处理总结错误"""
        self.status_label.setText("")
        self.setEnabled(True)
        QMessageBox.critical(self, "错误", f"获取消息失败: {error}")
        
    def send_to_group(self):
        """发送总结到群聊"""
        group_name = self.group_name_input.text()
        summary = self.summary_edit.toPlainText()
        
        if not group_name:
            QMessageBox.warning(self, "警告", "请输入群聊名称")
            return
        
        if not summary:
            QMessageBox.warning(self, "警告", "没有可发送的内容")
            return
        
        try:
            # 更新UI状态
            sender = self.sender()
            if isinstance(sender, QPushButton):
                original_text = sender.text()
                sender.setText("发送中...")
                sender.setEnabled(False)
            self.status_label.setText("正在发送到群聊，请稍候...")
            self.setEnabled(False)
            QApplication.processEvents()  # 确保UI更新
            
            # 发送消息
            success = send_summary(group_name, summary)
            
            # 恢复UI状态
            if isinstance(sender, QPushButton):
                sender.setText(original_text)
                sender.setEnabled(True)
            self.status_label.setText("")
            self.setEnabled(True)
            
            # 显示结果
            if success:
                QMessageBox.information(self, "成功", "总结已发送到群聊")
            else:
                QMessageBox.warning(self, "警告", "发送失败")
            
        except Exception as e:
            # 发生错误时恢复UI状态
            if isinstance(sender, QPushButton):
                sender.setText(original_text)
                sender.setEnabled(True)
            self.status_label.setText("")
            self.setEnabled(True)
            QMessageBox.critical(self, "错误", f"发送失败: {str(e)}")

    def save_summary(self):
        """保存总结到文件"""
        summary = self.summary_edit.toPlainText()
        group_name = self.group_name_input.text()
        
        if not summary:
            QMessageBox.warning(self, "警告", "没有可保存的内容")
            return
        
        if not group_name:
            QMessageBox.warning(self, "警告", "请输入群聊名称")
            return
        
        try:
            # 更新UI状态
            sender = self.sender()
            if isinstance(sender, QPushButton):
                original_text = sender.text()
                sender.setText("保存中...")
                sender.setEnabled(False)
            self.status_label.setText("正在保存文件，请稍候...")
            QApplication.processEvents()
            
            # 保存文件
            saved_file = save_summary(group_name, summary)
            
            # 恢复UI状态
            if isinstance(sender, QPushButton):
                sender.setText(original_text)
                sender.setEnabled(True)
            self.status_label.setText("")
            
            # 显示结果
            if saved_file:
                QMessageBox.information(self, "成功", f"总结已保存到: {saved_file}")
            else:
                QMessageBox.warning(self, "警告", "保存失败")
            
        except Exception as e:
            # 发生错误时恢复UI状态
            if isinstance(sender, QPushButton):
                sender.setText(original_text)
                sender.setEnabled(True)
            self.status_label.setText("")
            QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")

    def delete_service_config(self, service_name):
        """删除服务配置"""
        try:
            # 从配置中删除服务
            if service_name in self.ai_config.configs:
                del self.ai_config.configs[service_name]
            if service_name in AIServiceConfig.SERVICES:
                AIServiceConfig.SERVICES.clear()
            
            # 保存配置
            self.ai_config.save_configs()
            
            # 更新UI
            self.update_service_combo()
            self.update_config_cards()
            
            # 如果删除的是当前选中的服务，清空选择
            if self.service_combo.currentText() == "":
                self.ai_config.last_service = ""
                self.ai_config.save_configs()
            
            # 更新状态
            if hasattr(self, 'status_label') and self.status_label:
                self.status_label.setText(f"已删除服务: {service_name}")
                QTimer.singleShot(2000, lambda: self.status_label.setText(""))
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"删除服务失败: {str(e)}")

# 添加自定义ComboBox类
class CustomComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QComboBox {
                padding-right: 20px; /* 为下拉箭头留出空间 */
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: url(:/dropdown.png); /* 可以自定义下拉箭头图标 */
                width: 12px;
                height: 12px;
            }
        """)
    
    def mousePressEvent(self, event):
        """重写鼠标点击事件"""
        if event.button() == Qt.RightButton:
            # 右键点击时触发上下文菜单
            self.customContextMenuRequested.emit(event.pos())
        else:
            # 其他情况保持默认行为
            super().mousePressEvent(event)

def main():
    app = QApplication(sys.argv)
    
    # 设置应用程序级别的字体
    font = QFont(ModernStyle.FONT_FAMILY.split(',')[0].strip())
    app.setFont(font)
    app.setWindowIcon(QIcon(":/wechat.ico"))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 
