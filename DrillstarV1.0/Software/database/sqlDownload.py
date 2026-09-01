import os
from PyQt5.QtWidgets import QWidget,QFileDialog,QMessageBox
from PyQt5.QtCore import pyqtSignal
from database.ui.sqlDownload_ui import Ui_sqlDownload
from database.share_DataBase import ShareInfo
import pymysql
import pandas as pd

class Win_SQldownload(QWidget):
    msg_Signal = pyqtSignal(str, int)
    def __init__(self):
        super().__init__()
        self.ui = Ui_sqlDownload()
        self.ui.setupUi(self)

        self.ui.btn_ShowTables.clicked.connect(self.on_loadTables)
        self.ui.btn_Download.clicked.connect(self.on_Download)


    def on_loadTables(self):
        if ShareInfo.sql_cfg == {}:
            QMessageBox.critical(self, "错误", "未连接数据库！")
            msg = '---->未连接数据库！'
            self.msg_Signal.emit(msg, 1)
            return
        self.ui.cB_Tables.clear()
        for i in ShareInfo.sql_Tables:
            child1 = (str(i[0]))
            self.ui.cB_Tables.addItem(child1)

    def on_Download(self):
        if ShareInfo.sql_cfg == {}:
            QMessageBox.critical(self, "错误", "未连接数据库！")
            msg = '---->未连接数据库！'
            self.msg_Signal.emit(msg, 1)
            return
        conn = ShareInfo.DBconnect()
        cur = conn.cursor()
        try:
            filename, _ = QFileDialog.getSaveFileName(self, 'Save File', 'e:/', 'Data File(.*csv)')
            if filename != "":
                filename = filename + '.csv'
                tablename = self.ui.cB_Tables.currentText()
                sql = "SELECT * FROM {}".format(tablename)
                cur.execute(sql)
                data = cur.fetchall()
                des = cur.description
                header = []
                for item in des: header.append(item[0])
                self.df = pd.DataFrame(list(data))
                self.df.columns = header  # 替换表头
                self.df.to_csv(filename, encoding="utf-8", index=False)
                QMessageBox.information(self, '保存文件', '保存成功！')
                msg = '---->保存文件 {} 成功'.format(filename)
                self.msg_Signal.emit(msg, 0)
                cur.close()
            else:
                QMessageBox.critical(self, '错误', '选择文件错误！')
                msg = '---->选择文件错误！'
                self.msg_Signal.emit(msg, 1)
        except Exception as e:
            print("---->选择文件错误：{}".format(e))
            msg = "---->选择文件错误：{}".format(e)
            self.msg_Signal.emit(msg, 1)