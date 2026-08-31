import os
import json
import pymysql
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import pyqtSignal, QObject


class ShareInfo:
    subWinTable = {}  # 子窗口
    sql_cfg = {}
    sql_cfg_default = {
        'DB': "oilfile",
        'HOST': "localhost",
        'PORT': "3306",
        'USER': "root",
        'PASSWD': "119aab19abba91"
    }
    sql_isConnect = False
    sql_db = None
    sql_cursor = None
    sql_Tables = None

    KEYS_TYPE = {
        'object': 'VARCHAR(255)',
        'int64': 'INT',
        'float64': 'FLOAT',
        'int32': 'INT',
        'float32': 'FLOAT',
        'bool': 'TINYINT(1)',
        'datetime64[ns]': 'DATETIME',
        'timedelta64[ns]': 'VARCHAR(255)',
        '': 'VARCHAR(255)'
    }

    @staticmethod
    def DBconnect():
        """创建数据库连接（强制utf8mb4，设置超时）"""
        if ShareInfo.sql_cfg != {}:
            try:
                db = pymysql.connect(
                    host=ShareInfo.sql_cfg['HOST'],
                    port=int(ShareInfo.sql_cfg['PORT']),
                    user=ShareInfo.sql_cfg['USER'],
                    passwd=ShareInfo.sql_cfg['PASSWD'],
                    db=ShareInfo.sql_cfg['DB'],
                    charset='utf8mb4',
                    cursorclass=pymysql.cursors.Cursor,
                    connect_timeout=10,  # 连接超时
                    read_timeout=30,  # 读取超时
                    write_timeout=30  # 写入超时
                )
                # 强制设置会话字符集
                with db.cursor() as cur:
                    cur.execute("SET NAMES utf8mb4;")
                    cur.execute("SET character_set_connection = utf8mb4;")
                return db
            except Exception as e:
                # 子线程中不弹QMessageBox，改用信号传递错误
                print(f"数据库连接错误：{e}")
                return None
        else:
            return None

    @staticmethod
    def delete_table(tablename):
        """
        删除数据库中的指定表
        :param tablename: 要删除的表名
        :return: (bool, str) - 成功返回(True, 提示信息)，失败返回(False, 错误信息)
        """
        # 检查数据库配置
        if ShareInfo.sql_cfg == {}:
            return (False, "未连接数据库，无法删除表！")

        # 检查表名合法性
        if not tablename or tablename.strip() == "":
            return (False, "表名不能为空！")

        conn = None
        cur = None
        try:
            conn = ShareInfo.DBconnect()
            if conn is None:
                return (False, "数据库连接失败！")

            cur = conn.cursor()

            # 检查表是否存在
            check_sql = """
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = %s AND table_name = %s
            """
            cur.execute(check_sql, (ShareInfo.sql_cfg['DB'], tablename.strip()))
            if not cur.fetchone():
                return (False, f"表 {tablename} 不存在！")

            # 执行删除表
            drop_sql = f"DROP TABLE IF EXISTS `{tablename.strip()}`;"
            cur.execute(drop_sql)
            conn.commit()

            return (True, f"表 {tablename} 删除成功！")

        except pymysql.MySQLError as e:
            err_msg = f"删除失败：{e.args[1]}（错误码：{e.args[0]}）"
            if conn:
                conn.rollback()
            return (False, err_msg)
        except Exception as e:
            if conn:
                conn.rollback()
            return (False, f"删除异常：{str(e)}")
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    @staticmethod
    def get_all_tables():
        """获取数据库中所有表名"""
        if ShareInfo.sql_cfg == {}:
            return []

        conn = None
        cur = None
        try:
            conn = ShareInfo.DBconnect()
            if conn is None:
                return []

            cur = conn.cursor()
            cur.execute(f"SHOW TABLES FROM `{ShareInfo.sql_cfg['DB']}`;")
            tables = [table[0] for table in cur.fetchall()]
            ShareInfo.sql_Tables = tables
            return tables

        except Exception as e:
            print(f"获取表列表错误：{e}")
            return []
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()


class mySignal(QObject):
    getTables = pyqtSignal()
    tableDeleted = pyqtSignal(bool, str)  # 表删除完成信号