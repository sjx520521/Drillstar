import os
from PyQt5 import QtGui
from PyQt5.QtWidgets import QWidget,QMessageBox
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import pyqtSignal
from database.ui.sqlConnect_ui import Ui_SqlConnect
import pymysql
from database.share_DataBase import ShareInfo


class Win_SQlconnect(QWidget):
    getTables = pyqtSignal()
    msg_Signal = pyqtSignal(str,int)
    def __init__(self):
        super().__init__()
        self.ui = Ui_SqlConnect()
        self.ui.setupUi(self)

        self.ui.lE_Server.setText(ShareInfo.sql_cfg_default['HOST'])
        self.ui.lE_Port.setText(ShareInfo.sql_cfg_default['PORT'])
        self.ui.lE_Database.setText(ShareInfo.sql_cfg_default['DB'])
        self.ui.lE_Username.setText(ShareInfo.sql_cfg_default['USER'])
        self.ui.lE_Password.setText(ShareInfo.sql_cfg_default['PASSWD'])


        self.ui.btn_Connect.clicked.connect(self.on_Connect)




    def on_Connect(self):
        DBNAME = self.ui.lE_Database.text()
        DBHOST = self.ui.lE_Server.text()
        DBPORT = int(self.ui.lE_Port.text())
        DBUSER = self.ui.lE_Username.text()
        DBPASS = self.ui.lE_Password.text()
        try:
            self.db = pymysql.connect(host=DBHOST, port=DBPORT, user=DBUSER, passwd=DBPASS, database=DBNAME)
            QMessageBox.information(self, '连接', str(DBNAME) + '数据库连接成功')
            msg = '---->数据库：'+str(DBNAME) + '连接成功'
            self.msg_Signal.emit(msg, 0)
            ShareInfo.sql_isConnect = True
            self.on_LoadTables()
        except Exception as e:
            QMessageBox.critical(self, '错误', '连接数据库错误！')
            ShareInfo.sql_isConnect = False
            print('---->数据库连接失败：{}'.format(e))
            msg = '---->数据库连接失败：{}'.format(e)
            self.msg_Signal.emit(msg,1)
        self.on_ChangeStatus()


    def on_LoadTables(self):
        ShareInfo.sql_cfg['DB'] = self.ui.lE_Database.text()
        ShareInfo.sql_cfg['HOST'] = self.ui.lE_Server.text()
        ShareInfo.sql_cfg['PORT'] = int(self.ui.lE_Port.text())
        ShareInfo.sql_cfg['USER'] = self.ui.lE_Username.text()
        ShareInfo.sql_cfg['PASSWD'] = self.ui.lE_Password.text()

        self.cursor = self.db.cursor()
        sql = "SHOW TABLES"
        self.cursor.execute(sql)
        data = self.cursor.fetchall()
        ShareInfo.sql_Tables = data
        self.getTables.emit()




    def on_ChangeStatus(self):
        if ShareInfo.sql_isConnect:
            icon = QPixmap("icon/success.png")
            icon = icon.scaled(23,23)
            self.ui.label_status.setPixmap(icon)
        else:
            icon = QPixmap("icon/fall.png")
            icon = icon.scaled(23, 23)
            self.ui.label_status.setPixmap(icon)


    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        subWindow = ShareInfo.subWinTable['SqlConnect']['subWindow']
        subWindow.hide()
        a0.ignore()