import os
import sys
from datetime import datetime
from pathlib import Path

from PyQt5 import QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QIcon, QTextCursor
from PyQt5.QtWidgets import QApplication, QMessageBox, QWidget


def _get_app_base_dir():
    """Resolve the runtime base directory for both source and packaged runs."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


APP_BASE_DIR = _get_app_base_dir()
os.chdir(APP_BASE_DIR)

from dataanalysis.share_DataAnalysis import ShareInfo
from loading import LoadingProgress
from ui.main_ui import Ui_main


class Win_Main(QWidget):
    def __init__(self):
        super().__init__()
        self.ui = Ui_main()
        self.ui.setupUi(self)
        self._apply_branding()
        self._apply_layout()

        self.win_datascope = None
        self.win_database = None
        self.win_dataanalysis = None
        self.ui.btn_simulation_experiment.clicked.connect(self.on_SimulationExperiment_Click)
        self.ui.btn_data_management.clicked.connect(self.on_DataManagement_Click)
        self.ui.btn_data_analysis.clicked.connect(self.on_DataAnalysis)

        self.loading = LoadingProgress()
        self._init_operation_record()

    def _app_icon(self):
        icon_path = APP_BASE_DIR / "icon" / "app.ico"
        return QIcon(str(icon_path)) if icon_path.exists() else QIcon()

    def _apply_branding(self):
        self.setWindowIcon(self._app_icon())
        self.setWindowTitle("DrillStar 钻井数据采集分析平台")
        self.ui.label.setText("DrillStar")
        self.ui.label_2.setText("开始使用")
        self.ui.label_3.setText("操作记录")
        self.ui.btn_simulation_experiment.setText("模拟实验")
        self.ui.btn_data_management.setText("数据管理")
        self.ui.btn_data_analysis.setText("数据分析")
        self.ui.btn_simulation_experiment.setIcon(QIcon(str(APP_BASE_DIR / "icon" / "data_collection.png")))
        self.ui.btn_data_management.setIcon(QIcon(str(APP_BASE_DIR / "icon" / "data_management.png")))
        self.ui.btn_data_analysis.setIcon(QIcon(str(APP_BASE_DIR / "icon" / "data_analysis.png")))
        self.ui.te_operating_record.setReadOnly(True)

        title_font = QFont("Microsoft YaHei", 34)
        title_font.setBold(True)
        section_font = QFont("Microsoft YaHei", 16)
        section_font.setBold(True)
        button_font = QFont("Microsoft YaHei", 22)
        button_font.setBold(True)
        text_font = QFont("Microsoft YaHei", 12)

        self.ui.label.setFont(title_font)
        self.ui.label_2.setFont(section_font)
        self.ui.label_3.setFont(section_font)
        self.ui.btn_simulation_experiment.setFont(button_font)
        self.ui.btn_data_management.setFont(button_font)
        self.ui.btn_data_analysis.setFont(button_font)
        self.ui.te_operating_record.setFont(text_font)

    def _init_operation_record(self):
        self.ui.te_operating_record.clear()
        self._log_operation("系统启动，进入主界面。")
        self._log_operation("请选择模拟实验、数据管理或数据分析模块。")

    def _log_operation(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.ui.te_operating_record.append(f"[{timestamp}] {message}")
        self.ui.te_operating_record.moveCursor(QTextCursor.End)

    def _show_after_child_closed(self, module_name):
        self.show()
        self._log_operation(f"{module_name}模块已关闭，返回主界面。")

    def _apply_layout(self):
        self.setStyleSheet(
            """
            QWidget {
                background: #eef1f4;
                color: #1f2933;
                font-family: "Microsoft YaHei";
            }
            QLabel#label {
                color: #1b2733;
            }
            QLabel#label_2, QLabel#label_3 {
                color: #263645;
                font-size: 16px;
                font-weight: 600;
            }
            QPushButton {
                background: #f8fafc;
                color: #1b2733;
                border: 1px solid #9aa7b3;
                border-radius: 3px;
                padding: 10px 14px;
                text-align: left;
            }
            QPushButton:hover {
                background: #e7edf3;
                border-color: #64748b;
            }
            QPushButton:pressed {
                background: #d5dee8;
            }
            QTextEdit {
                background: #f8fafc;
                border: 1px solid #9aa7b3;
                border-radius: 3px;
                padding: 10px;
                color: #263645;
            }
            """
        )

        self.ui.label.setGeometry(QtCore.QRect(24, 18, 280, 56))
        self.ui.label.setStyleSheet("color: #1b2733; font-size: 34px; font-weight: 700;")
        self.ui.label_2.setGeometry(QtCore.QRect(24, 92, 140, 32))
        self.ui.label_2.setStyleSheet("color: #263645; font-size: 16px; font-weight: 600;")
        self.ui.label_3.setGeometry(QtCore.QRect(314, 92, 140, 32))
        self.ui.label_3.setStyleSheet("color: #263645; font-size: 16px; font-weight: 600;")

        for button, y in [
            (self.ui.btn_simulation_experiment, 140),
            (self.ui.btn_data_management, 240),
            (self.ui.btn_data_analysis, 340),
        ]:
            button.setGeometry(QtCore.QRect(20, y, 270, 84))
            button.setIconSize(QtCore.QSize(42, 42))
            button.setStyleSheet(
                """
                QPushButton {
                    background: #f8fafc;
                    color: #1b2733;
                    border: 1px solid #7f8b98;
                    border-left: 4px solid #1f4e79;
                    border-radius: 3px;
                    font-size: 22px;
                    font-weight: 600;
                    padding-left: 18px;
                    text-align: left;
                }
                QPushButton:hover {
                    background: #e7edf3;
                    border-color: #334155;
                    border-left: 4px solid #123a5c;
                }
                QPushButton:pressed {
                    background: #d5dee8;
                }
                """
            )

        self.ui.te_operating_record.setGeometry(QtCore.QRect(314, 140, 352, 284))
        self.ui.te_operating_record.setStyleSheet(
            """
            QTextEdit {
                background: #f8fafc;
                color: #263645;
                border: 1px solid #9aa7b3;
                border-radius: 3px;
                padding: 10px;
                font-size: 14px;
            }
            """
        )

    def on_SimulationExperiment_Click(self):
        self._log_operation("正在打开模拟实验模块。")
        try:
            from datascope.datascope_main import Win_DataScope

            self.win_datascope = Win_DataScope()
            self.win_datascope.closed.connect(lambda: self._show_after_child_closed("模拟实验"))
            self.win_datascope.show()
            self.hide()
            self._log_operation("模拟实验模块已打开。")
        except Exception as e:
            self._log_operation(f"模拟实验模块打开失败：{e}")
            QMessageBox.critical(self, "错误", f"模拟实验模块打开失败：{e}")

    def on_DataManagement_Click(self):
        self._log_operation("正在打开数据管理模块。")
        try:
            from database.database_main import Win_DataBase

            self.win_database = Win_DataBase()
            self.win_database.closed.connect(lambda: self._show_after_child_closed("数据管理"))
            self.win_database.show()
            self.hide()
            self._log_operation("数据管理模块已打开。")
        except Exception as e:
            self._log_operation(f"数据管理模块打开失败：{e}")
            QMessageBox.critical(self, "错误", f"数据管理模块打开失败：{e}")

    def on_DataAnalysis(self):
        self._log_operation("正在打开数据分析模块。")
        try:
            from dataanalysis.dataAnalysis_main import Win_DataAnalysis

            self.win_dataanalysis = Win_DataAnalysis()
            self.win_dataanalysis.closed.connect(lambda: self._show_after_child_closed("数据分析"))
            self.win_dataanalysis.show()
            self.hide()
            self._log_operation("数据分析模块已打开。")
        except Exception as e:
            self._log_operation(f"数据分析模块打开失败：{e}")
            QMessageBox.critical(self, "错误", f"数据分析模块打开失败：{e}")

    def on_loading(self):
        self.loading.show()


if __name__ == "__main__":
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_EnableHighDpiScaling)

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(APP_BASE_DIR / "icon" / "app.ico")))
    window = Win_Main()

    ShareInfo.app = app

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

    window.show()
    sys.exit(app.exec_())
