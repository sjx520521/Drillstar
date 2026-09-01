from PyQt5.QtCore import QThread, pyqtSignal  # 需导入相关模块
import pymysql
import pandas as pd

class SQLQueryThread(QThread):
    """数据库查询线程"""
    # 定义信号：查询完成时传递DataFrame
    finished_signal = pyqtSignal(pd.DataFrame)
    # 定义信号：查询出错时传递错误信息
    error_signal = pyqtSignal(str)

    def __init__(self, db_conn, table_name):
        super().__init__()
        self.db_conn = db_conn  # 数据库连接对象
        self.table_name = table_name  # 要查询的表名

    def run(self):
        """线程执行的核心方法（耗时操作放这里）"""
        try:
            # 创建游标（使用上下文管理器自动关闭）
            with self.db_conn.cursor() as cursor:
                # 表名加反引号，防止特殊字符/关键字问题
                sql = f"SELECT * FROM `{self.table_name}`"
                cursor.execute(sql)

                # 【关键优化】分批读取数据，避免一次性加载大量数据到内存
                chunk_size = 1000  # 每批读取1000行，可根据需求调整
                chunks = []
                while True:
                    chunk = cursor.fetchmany(chunk_size)
                    if not chunk:
                        break
                    chunks.append(chunk)

                # 处理空数据
                if not chunks:
                    self.error_signal.emit("查询结果为空，无数据可导入")
                    return

                # 合并所有批次数据
                data = [row for chunk in chunks for row in chunk]
                # 获取列名
                columns = [desc[0] for desc in cursor.description]
                # 构建DataFrame
                df = pd.DataFrame(data, columns=columns)

                # 发送结果到主线程
                self.finished_signal.emit(df)

        except pymysql.Error as e:
            self.error_signal.emit(f"数据库查询失败：{e.args[1]}")
        except Exception as e:
            self.error_signal.emit(f"查询异常：{str(e)}")