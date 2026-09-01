import os
import pandas as pd
import numpy as np
import pymysql
import logging
import datetime  # 新增：用于判断时间类型
from PyQt5.QtWidgets import (
    QWidget, QMessageBox, QLabel, QApplication
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QPointF
)

from dataanalysis.buttonNode import ButtonNode
from dataanalysis.ui.sqlimport_ui import Ui_SQLimport
from dataanalysis.share_DataAnalysis import ShareInfo

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# 定义常量，增强代码可维护性
CHUNK_SIZE = 1000  # 分批查询的块大小
DEFAULT_DB_PORT = 3306  # 默认数据库端口
ICON_SUCCESS_PATH = "icon/success.png"  # 成功图标路径
ICON_FAIL_PATH = "icon/fall.png"  # 失败图标路径
# 时间列名（包含中文和英文，用于识别时间列）
TIME_COLUMN_NAMES = {'时间', 'date', 'datetime', 'timestamp', 'create_time', 'update_time', '创建时间', '更新时间'}


# 数据库查询线程类
class SQLQueryThread(QThread):
    """数据库查询线程，避免主线程阻塞"""
    finished_signal = pyqtSignal(pd.DataFrame)  # 查询成功信号
    error_signal = pyqtSignal(str)  # 查询失败信号

    def __init__(self, db_config, table_name):
        """
        初始化查询线程
        :param db_config: 数据库连接配置字典
        :param table_name: 要查询的表名
        """
        super().__init__()
        self.db_config = db_config  # 数据库连接配置（替代共享连接，保证线程安全）
        self.table_name = table_name  # 要查询的表名
        self._is_running = True  # 优雅停止标志位

    def stop(self):
        """优雅停止线程"""
        self._is_running = False

    def run(self):
        """线程执行的核心方法"""
        conn = None
        try:
            # 1. 线程内创建独立的数据库连接（解决线程安全问题）
            conn = pymysql.connect(**self.db_config)
            if not conn.open:
                self.error_signal.emit("数据库连接已断开")
                return

            # 2. 使用上下文管理器自动关闭游标
            with conn.cursor() as cursor:
                # 先获取表的所有列名，排除id列
                cursor.execute(f"DESCRIBE `{self.table_name}`")
                columns = [col[0] for col in cursor.fetchall() if col[0] != 'id']
                if not columns:
                    self.error_signal.emit("表中无有效列（排除id后）")
                    return

                # 构造排除id的查询SQL
                columns_str = ', '.join([f"`{col}`" for col in columns])
                sql = f"SELECT {columns_str} FROM `{self.table_name}`"
                cursor.execute(sql)

                # 获取列类型（用于精准识别时间列）
                column_types = [desc[1] for desc in cursor.description]
                from pymysql.constants import FIELD_TYPE
                time_field_types = {FIELD_TYPE.DATE, FIELD_TYPE.DATETIME, FIELD_TYPE.TIMESTAMP, FIELD_TYPE.TIME}
                time_columns_by_type = [cursor.description[i][0] for i, typ in enumerate(column_types) if typ in time_field_types]

                # 3. 分批读取数据，降低内存占用
                chunks = []
                while self._is_running:
                    chunk = cursor.fetchmany(CHUNK_SIZE)
                    if not chunk:
                        break
                    chunks.append(chunk)

                # 线程被停止则直接返回
                if not self._is_running:
                    self.error_signal.emit("查询已被用户终止")
                    return

                # 处理空数据
                if not chunks:
                    self.error_signal.emit("查询结果为空，无数据可导入")
                    return

                # 4. 合并所有批次数据并构建DataFrame
                data = [row for chunk in chunks for row in chunk]
                df = pd.DataFrame(data, columns=columns)

                """
                强化数据清洗：保留时间列，仅转换数值列
                """
                logger.info(f"原始查询数据形状：{df.shape}，数据类型：\n{df.dtypes}")

                # 识别时间列（四重保障：字段类型 + 数据类型 + 列名精确匹配 + 列名包含）
                time_columns = set(time_columns_by_type)
                for col in df.columns:
                    # 方式1：列名精确匹配时间列名
                    if col in TIME_COLUMN_NAMES:
                        time_columns.add(col)
                        continue
                    # 方式2：列名包含时间关键词
                    if any(keyword in col.lower() for keyword in ['time', 'date', 'datetime', 'timestamp']):
                        time_columns.add(col)
                        continue
                    # 方式3：根据数据类型判断
                    try:
                        # 尝试转换为时间类型，能转换的视为时间列
                        pd.to_datetime(df[col], errors='raise')
                        time_columns.add(col)
                    except (ValueError, TypeError):
                        # 检查是否为datetime对象
                        if df[col].apply(lambda x: isinstance(x, (pd.Timestamp, datetime.datetime))).any():
                            time_columns.add(col)
                time_columns = list(time_columns)
                non_time_columns = [col for col in df.columns if col not in time_columns]

                logger.info(f"识别出时间列：{time_columns}")

                # 1. 空值替换（仅对非时间列生效）
                df[non_time_columns] = df[non_time_columns].replace([None, '', ' '], np.nan)

                # 2. 仅对非时间列尝试转换为数值类型
                for col in non_time_columns:
                    try:
                        # 用coerce替代raise，避免单个值错误导致整列转换失败
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                        logger.info(f"列{col}成功转换为数值类型，新类型：{df[col].dtype}")
                    except (ValueError, TypeError):
                        logger.warning(f"列{col}无法转换为数值类型，保留原类型")
                        continue

                # 3. 删除全为空的列（修复核心：删除列时无需指定subset，直接按列全空删除）
                df = df.dropna(axis=1, how='all')
                # 4. 重置索引
                df = df.reset_index(drop=True)

                logger.info(f"清洗后数据形状：{df.shape}，数据类型：\n{df.dtypes}")

                # 5. 发送结果到主线程
                self.finished_signal.emit(df)

        except pymysql.Error as e:
            self.error_signal.emit(f"数据库查询失败：{e.args[1]}")
            logger.error(f"数据库查询失败：{e}")
        except Exception as e:
            self.error_signal.emit(f"查询异常：{str(e)}")
            logger.error(f"查询异常：{e}", exc_info=True)
        finally:
            # 关闭线程内的连接，释放资源
            if conn:
                try:
                    conn.close()
                except Exception as e:
                    logger.warning(f"关闭线程内数据库连接失败：{e}")


class Win_SQLimport(QWidget):
    def __init__(self, node: ButtonNode):
        super().__init__()
        self.ui = Ui_SQLimport()
        self.ui.setupUi(self)
        self.ui.btn_Transfer.setText("Transfer")
        self.setWindowTitle("DataAnalysis [SQL Import]")
        self.setWindowState(Qt.WindowActive)
        self.setWindowModality(Qt.WindowModal)  # 改为WindowModal，避免阻塞整个应用

        # 核心变量初始化
        self.node = node
        self.df = pd.DataFrame()
        self.TablesList = []  # 存储表名字符串
        self.db = None  # 数据库连接对象
        self.query_thread = None  # 查询线程
        self.current_table = ""  # 保存当前选择的表名（用于构建title）

        # 初始化UI状态
        self.on_ChangeStatus()
        self.ui.btn_Transfer.setEnabled(False)

        # 加载全局配置的数据库信息
        self._load_global_db_config()

        # 添加加载提示标签
        self.tip_label = QLabel(self)
        self.tip_label.setAlignment(Qt.AlignCenter)
        self.tip_label.setStyleSheet("color: #666; font-size: 12px;")
        # 确保UI有verticalLayout布局（兼容不同的UI文件）
        if hasattr(self.ui, 'verticalLayout'):
            self.ui.verticalLayout.addWidget(self.tip_label)
        else:
            self.ui.layout().addWidget(self.tip_label)

        # 绑定按钮事件
        self.ui.btn_Connect.clicked.connect(self.on_Connect)
        self.ui.btn_Transfer.clicked.connect(self.on_Transfer)

        logger.info(f"SQL导入窗口初始化，关联节点：{self.node}")

    def _load_global_db_config(self):
        """加载全局数据库配置，增加容错"""
        self.ui.lE_Server.setText(getattr(ShareInfo, 'DBHOST', ''))
        self.ui.lE_Port.setText(getattr(ShareInfo, 'DBPORT', str(DEFAULT_DB_PORT)))
        self.ui.lE_Database.setText(getattr(ShareInfo, 'DBNAME', ''))
        self.ui.lE_Username.setText(getattr(ShareInfo, 'DBUSER', ''))
        self.ui.lE_Password.setText(getattr(ShareInfo, 'DBPASS', ''))

    def _load_icon(self, icon_path, size=(23, 23)):
        """
        安全加载图标，增加容错
        :param icon_path: 图标路径
        :param size: 图标大小 (width, height)
        :return: QPixmap or None
        """
        try:
            if not os.path.exists(icon_path):
                logger.warning(f"图标文件不存在：{icon_path}")
                return None
            pixmap = QPixmap(icon_path)
            return pixmap.scaled(size[0], size[1], Qt.KeepAspectRatio, Qt.SmoothTransformation)
        except Exception as e:
            logger.warning(f"加载图标失败：{e}")
            return None

    def on_ChangeStatus(self):
        """更新连接状态显示"""
        if ShareInfo.sql_isConnect:
            pixmap = self._load_icon(ICON_SUCCESS_PATH)
            if pixmap:
                self.ui.label_status.setPixmap(pixmap)
            else:
                self.ui.label_status.setText("已连接")
            # 仅当有表名时启用Transfer按钮
            self.ui.btn_Transfer.setEnabled(len(self.TablesList) > 0)
        else:
            pixmap = self._load_icon(ICON_FAIL_PATH)
            if pixmap:
                self.ui.label_status.setPixmap(pixmap)
            else:
                self.ui.label_status.setText("未连接")
            self.ui.btn_Transfer.setEnabled(False)

    def on_Connect(self):
        """连接数据库按钮点击事件"""
        # 获取用户输入的数据库信息（去除首尾空格）
        DBNAME = self.ui.lE_Database.text().strip()
        DBHOST = self.ui.lE_Server.text().strip()
        DBPORT_TEXT = self.ui.lE_Port.text().strip()
        DBUSER = self.ui.lE_Username.text().strip()
        DBPASS = self.ui.lE_Password.text().strip()

        # 空值校验
        if not DBHOST or not DBNAME or not DBUSER:
            QMessageBox.critical(self, '错误', '服务器、数据库名、用户名不能为空！')
            return

        # 端口转换异常处理
        try:
            DBPORT = int(DBPORT_TEXT) if DBPORT_TEXT else DEFAULT_DB_PORT
        except ValueError:
            QMessageBox.critical(self, '错误', '端口必须是数字！')
            return

        # 关闭旧连接（修复核心：增加None判断）
        if self.db is not None:
            try:
                if self.db.open:
                    self.db.close()
                    logger.info("旧数据库连接已关闭")
            except Exception as e:
                logger.warning(f"关闭旧数据库连接失败：{e}")

        # 尝试连接数据库
        try:
            self.db = pymysql.connect(
                host=DBHOST,
                port=DBPORT,
                user=DBUSER,
                passwd=DBPASS,
                database=DBNAME,
                charset='utf8mb4',
                connect_timeout=5,
                read_timeout=10
            )
            QMessageBox.information(self, '连接', f'{DBNAME} 数据库连接成功')
            ShareInfo.sql_isConnect = True

            # 清空原有表数据，避免重复
            self.TablesList.clear()
            self.ui.cB_Tables.clear()

            # 加载数据表名
            self.on_LoadTables()

        except pymysql.Error as e:
            err_msg = f'连接数据库错误：{e.args[1]}'
            QMessageBox.critical(self, '错误', err_msg)
            ShareInfo.sql_isConnect = False
            self.db = None
            # 清空表列表，更新UI
            self.TablesList.clear()
            self.ui.cB_Tables.clear()
            self.ui.cB_Tables.addItem("连接失败")
            self.ui.cB_Tables.setEnabled(False)
            logger.error(err_msg)
        except Exception as e:
            err_msg = f'未知错误：{str(e)}'
            QMessageBox.critical(self, '错误', err_msg)
            ShareInfo.sql_isConnect = False
            self.db = None
            # 清空表列表，更新UI
            self.TablesList.clear()
            self.ui.cB_Tables.clear()
            self.ui.cB_Tables.addItem("连接失败")
            self.ui.cB_Tables.setEnabled(False)
            logger.error(err_msg)
        finally:
            self.on_ChangeStatus()

    def on_LoadTables(self):
        """加载数据库中的表名"""
        if not ShareInfo.sql_isConnect or self.db is None:
            return

        try:
            # 使用上下文管理器管理游标
            with self.db.cursor() as cursor:
                sql = "SHOW TABLES"
                cursor.execute(sql)
                data = cursor.fetchall()

                # 存储表名字符串（修复核心匹配问题）
                for table in data:
                    table_name = table[0]
                    self.TablesList.append(table_name)
                    self.ui.cB_Tables.addItem(table_name)

                # 处理无表的情况
                if not self.TablesList:
                    self.ui.cB_Tables.addItem("无可用数据表")
                    self.ui.cB_Tables.setEnabled(False)
                else:
                    self.ui.cB_Tables.setEnabled(True)

                logger.info(f"数据库表名加载完成：{self.TablesList}")
                self.node.eval()

        except pymysql.Error as e:
            err_msg = f'加载表名失败：{e.args[1]}'
            QMessageBox.critical(self, '错误', err_msg)
            self.ui.cB_Tables.addItem("加载表名失败")
            self.ui.cB_Tables.setEnabled(False)
            logger.error(err_msg)
        except Exception as e:
            err_msg = f'加载表名异常：{str(e)}'
            QMessageBox.critical(self, '错误', err_msg)
            self.ui.cB_Tables.addItem("加载表名失败")
            self.ui.cB_Tables.setEnabled(False)
            logger.error(err_msg)

    def on_Transfer(self):
        """点击Transfer按钮的响应方法"""
        # 1. 获取当前选择的表名
        table_name = self.ui.cB_Tables.currentText().strip()
        self.current_table = table_name  # 保存当前表名

        # 调试打印
        logger.info(f"当前选择的表名：{table_name}")
        logger.info(f"TablesList内容：{self.TablesList}")
        logger.info(f"表名是否有效：{table_name in self.TablesList}")

        # 2. 验证表名有效性
        if not table_name or table_name not in self.TablesList:
            QMessageBox.critical(self, "错误", "请选择有效的数据表！")
            return

        # 3. 禁用按钮，防止重复点击
        self.ui.btn_Transfer.setEnabled(False)
        self.tip_label.setText("正在查询数据，请稍候...")
        QApplication.processEvents()  # 立即刷新UI

        # 4. 构建数据库连接配置（用于线程内创建连接）
        db_config = {
            'host': self.ui.lE_Server.text().strip(),
            'port': int(self.ui.lE_Port.text().strip() or DEFAULT_DB_PORT),
            'user': self.ui.lE_Username.text().strip(),
            'passwd': self.ui.lE_Password.text().strip(),
            'database': self.ui.lE_Database.text().strip(),
            'charset': 'utf8mb4',
            'connect_timeout': 5,
            'read_timeout': 10
        }

        # 5. 停止旧线程（如果存在）
        if self.query_thread and self.query_thread.isRunning():
            self.query_thread.stop()
            self.query_thread.wait(1000)
            logger.info("旧查询线程已终止")

        # 6. 创建并启动查询线程（传入配置而非共享连接）
        self.query_thread = SQLQueryThread(db_config, table_name)
        # 绑定信号与槽函数
        self.query_thread.finished_signal.connect(self.on_query_finished)
        self.query_thread.error_signal.connect(self.on_query_error)
        # 线程结束后恢复按钮状态
        self.query_thread.finished.connect(self.on_thread_finished)
        # 启动线程
        self.query_thread.start()

    def _get_node_position(self):
        """
        安全获取节点位置，彻底解决QPointF不可调用问题
        :return: (pos_x, pos_y)
        """
        pos_x = 0.0
        pos_y = 0.0
        try:
            # 优先从图形节点获取位置（更准确）
            if hasattr(self.node, 'grNode') and self.node.grNode:
                pos = self.node.grNode.pos()
                if isinstance(pos, QPointF):
                    # 兼容：先判断是否为方法，再调用/取值
                    pos_x = pos.x() if callable(getattr(pos, 'x')) else pos.x
                    pos_y = pos.y() if callable(getattr(pos, 'y')) else pos.y
            elif hasattr(self.node, 'pos'):
                pos = self.node.pos()
                if pos is not None:
                    pos_x = pos.x() if callable(getattr(pos, 'x')) else pos.x
                    pos_y = pos.y() if callable(getattr(pos, 'y')) else pos.y
        except Exception as e:
            logger.warning(f"获取节点位置失败（非致命）：{e}")
        return pos_x, pos_y

    def on_query_finished(self, df):
        self.df = df
        logger.info(f"SQL数据加载完成，数据形状：{df.shape}")

        try:
            # 空数据校验
            if df.empty:
                QMessageBox.warning(self, "警告", "数据为空，无法加载到节点")
                self.node.markInvalid()
                self.tip_label.setText("数据导入失败：数据为空")
                return

            # 加载数据到节点
            if self.node.LoadData(df):
                # 关键：标记节点为有效
                self.node.markValid()

                # 安全获取节点位置
                pos_x, pos_y = self._get_node_position()

                # 确保序列化格式包含title键（解决datainfo的KeyError）和其他核心键
                def node_serialize():
                    """重写节点的序列化方法"""
                    # 调用父类的序列化方法，避免丢失原有字段
                    base_serialize = self.node.__class__.serialize(self.node) if hasattr(self.node.__class__, 'serialize') else {}
                    base_serialize.update({
                        'id': getattr(self.node, 'id', str(id(self.node))),
                        'type': getattr(self.node, 'type_', self.node.content_label_objname),
                        'title': f'SQL导入_{self.current_table}',
                        'value': df,
                        'position': (pos_x, pos_y)
                    })
                    return base_serialize

                # 保留原序列化方法，避免覆盖后无法恢复
                if not hasattr(self.node, '_original_serialize'):
                    self.node._original_serialize = self.node.serialize
                self.node.serialize = node_serialize

                # 触发节点计算
                self.node.eval()
                if hasattr(self.node, 'evalChildren'):
                    self.node.evalChildren()

                QMessageBox.information(self, "成功", f"数据导入成功！共导入 {len(df)} 行数据")
                self.tip_label.setText(f"数据导入完成，共 {len(df)} 行")
                logger.info("SQL数据成功加载到节点")
            else:
                raise RuntimeError("节点LoadData方法返回False")

        except Exception as e:
            err_msg = f"加载数据到节点失败：{str(e)}"
            QMessageBox.critical(self, "错误", err_msg)
            self.node.markInvalid()
            self.tip_label.setText("数据导入失败")
            logger.error(err_msg, exc_info=True)

    def on_query_error(self, error_msg):
        """查询失败的回调方法（主线程执行）"""
        QMessageBox.critical(self, "错误", error_msg)
        self.tip_label.setText(f"数据导入失败：{error_msg}")
        logger.error(f"数据查询失败：{error_msg}")

    def on_thread_finished(self):
        """线程结束后的清理工作"""
        self.ui.btn_Transfer.setEnabled(True)
        QApplication.processEvents()  # 立即刷新UI

    def closeEvent(self, event):
        """窗口关闭事件，释放资源"""
        try:
            # 1. 恢复节点原有的序列化方法
            if hasattr(self.node, '_original_serialize'):
                self.node.serialize = self.node._original_serialize
                delattr(self.node, '_original_serialize')

            # 2. 关闭数据库连接
            if self.db is not None:
                try:
                    if self.db.open:
                        self.db.close()
                        logger.info("数据库连接已关闭")
                except Exception as e:
                    logger.warning(f"关闭数据库连接失败：{e}")

            # 3. 优雅停止查询线程
            if self.query_thread and self.query_thread.isRunning():
                self.query_thread.stop()
                self.query_thread.wait(2000)
                if self.query_thread.isRunning():
                    self.query_thread.terminate()
                    self.query_thread.wait()
                logger.info("查询线程已终止")

            # 4. 重置全局连接状态
            ShareInfo.sql_isConnect = False

            logger.info("SQL导入窗口已安全关闭")
        except Exception as e:
            logger.error(f"关闭窗口时发生错误：{e}", exc_info=True)

        event.accept()
