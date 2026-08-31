import os
import math
import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QFileDialog, QMessageBox, QProgressBar
)
from PyQt5.QtCore import pyqtSignal, Qt, QThread
import pandas as pd
from dataanalysis.ui.saveData_ui import Ui_saveData
from dataanalysis.buttonNode import ButtonNode


# 定义保存数据的子线程类
class SaveDataThread(QThread):
    # 定义进度更新信号（传递当前进度值）和完成信号（传递是否成功）
    progress_update = pyqtSignal(int)
    save_finished = pyqtSignal(bool, str)

    def __init__(self, df, file_path, file_format="csv", chunk_size=1000):
        super().__init__()
        self.df = df  # 要保存的数据
        self.file_path = file_path  # 保存路径
        self.file_format = file_format  # 文件格式（csv/xlsx）
        self.chunk_size = chunk_size  # 分块大小
        self.is_running = True  # 线程运行标志

    def run(self):
        try:
            total_rows = len(self.df)
            # 空数据处理
            if total_rows == 0:
                if self.file_format == "csv":
                    self.df.to_csv(self.file_path, encoding="utf-8", index=False)
                else:
                    self.df.to_excel(self.file_path, index=False)
                self.progress_update.emit(100)
                self.save_finished.emit(True, "保存成功：空数据文件")
                return

            # 初始化进度（参考CSVImport的分步更新）
            self.progress_update.emit(5)

            # 根据文件格式分块保存
            if self.file_format == "csv":
                self._save_csv(total_rows)
            else:
                self._save_excel(total_rows)

            if self.is_running:
                self.progress_update.emit(100)
                self.save_finished.emit(True, f"保存成功：共{total_rows}行数据")
            else:
                self.save_finished.emit(False, "保存被取消")

        except Exception as e:
            self.save_finished.emit(False, f"保存失败：{str(e)}")

    def _save_csv(self, total_rows):
        """优化的CSV分块保存，提升进度条流畅度"""
        total_chunks = math.ceil(total_rows / self.chunk_size)
        self.progress_update.emit(10)  # 进入CSV保存阶段

        # 先写入表头（单独处理，保证表头只写一次）
        header = self.df.columns.tolist()
        with open(self.file_path, 'w', encoding='utf-8', newline='') as f:
            f.write(','.join(header) + '\n')

        self.progress_update.emit(15)  # 表头写入完成

        # 分块写入数据行
        processed_rows = 0
        for i in range(total_chunks):
            if not self.is_running:
                break
            start = i * self.chunk_size
            end = min((i + 1) * self.chunk_size, total_rows)
            chunk = self.df.iloc[start:end]

            # 写入数据块（使用csv模块更高效，避免pandas的模式问题）
            chunk.to_csv(
                self.file_path,
                encoding="utf-8",
                index=False,
                mode='a',
                header=False
            )

            # 更新已处理行数
            processed_rows += len(chunk)
            # 计算进度：15% ~ 90% 分配给数据写入
            current_progress = 15 + int((processed_rows / total_rows) * 75)
            self.progress_update.emit(min(current_progress, 90))

        # 数据写入完成，进度到95%
        if self.is_running:
            self.progress_update.emit(95)

    def _save_excel(self, total_rows):
        """修复的Excel分块保存，使用openpyxl实现高效追加"""
        self.progress_update.emit(10)  # 进入Excel保存阶段

        # 第一步：写入首块数据（包含表头）
        start = 0
        end = min(self.chunk_size, total_rows)
        first_chunk = self.df.iloc[start:end]
        first_chunk.to_excel(self.file_path, sheet_name='data', index=False)
        self.progress_update.emit(15)  # 首块写入完成

        # 第二步：使用openpyxl追加剩余数据
        try:
            from openpyxl import load_workbook
            wb = load_workbook(self.file_path)
            ws = wb['data']
            start_row = ws.max_row + 1  # 下一个写入的行号

            processed_rows = len(first_chunk)
            total_chunks = math.ceil(total_rows / self.chunk_size)

            for i in range(1, total_chunks):
                if not self.is_running:
                    wb.close()
                    break
                start = i * self.chunk_size
                end = min((i + 1) * self.chunk_size, total_rows)
                chunk = self.df.iloc[start:end]

                # 逐行写入数据
                for _, row in chunk.iterrows():
                    ws.append(row.tolist())

                # 更新已处理行数
                processed_rows += len(chunk)
                # 计算进度：15% ~ 90% 分配给数据写入
                current_progress = 15 + int((processed_rows / total_rows) * 75)
                self.progress_update.emit(min(current_progress, 90))

            # 保存工作簿
            if self.is_running:
                wb.save(self.file_path)
            wb.close()

        except ImportError:
            # 备用方案：使用pandas分块写入（效率较低，但兼容）
            self.progress_update.emit(20)
            total_chunks = math.ceil(total_rows / self.chunk_size)
            for i in range(total_chunks):
                if not self.is_running:
                    break
                start = i * self.chunk_size
                end = min((i + 1) * self.chunk_size, total_rows)
                chunk = self.df.iloc[start:end]
                mode = 'w' if i == 0 else 'a'
                header = True if i == 0 else False
                with pd.ExcelWriter(self.file_path, engine='openpyxl', mode=mode) as writer:
                    chunk.to_excel(writer, sheet_name='data', index=False, header=header)
                # 计算进度
                current_progress = 15 + int((i + 1) / total_chunks * 75)
                self.progress_update.emit(min(current_progress, 90))

        # 数据写入完成，进度到95%
        if self.is_running:
            self.progress_update.emit(95)

    def stop(self):
        self.is_running = False


class Win_SaveData(QWidget):
    def __init__(self, node: ButtonNode):
        super().__init__()
        self.ui = Ui_saveData()
        self.ui.setupUi(self)
        self.setWindowTitle("DataAnalysis [Save Data]")
        self.node = node
        self.df = pd.DataFrame()
        self.save_thread = None  # 保存数据的线程

        # 绑定按钮事件
        self.ui.btn_Save.clicked.connect(self.on_Save)
        self.ui.btn_Load.clicked.connect(self.on_Load)

        # 初始状态：保存按钮禁用
        self.ui.btn_Save.setEnabled(False)

        # 进度条配置（参考CSVImport的样式）
        self.ui.progressBar.setRange(0, 100)
        self.ui.progressBar.setValue(0)
        self.ui.progressBar.setTextVisible(True)  # 显示进度百分比

    def on_Load(self):
        """加载上游节点数据（支持重复加载+添加加载提示框）"""
        # 1. 重置已有数据（支持重复加载，清空历史数据）
        self.df = pd.DataFrame()
        self.ui.label_info.setText("正在加载数据...")
        self.ui.btn_Save.setEnabled(False)
        self.ui.progressBar.setValue(0)

        if self.node.getInput(0) is None:
            self.node.markDirty()
            self.node.markInvalid()
            QMessageBox.warning(self, "警告", "上游节点无数据输入！")
            self.ui.label_info.setText("加载失败：上游节点无数据")
            return
        else:
            try:
                res = self.node.getInput(0).serialize()
                self.df = res.get('value', pd.DataFrame())
                self.node.eval()

                # 2. 显示加载的数据信息
                data_info = f"已加载数据：{len(self.df)}行 × {len(self.df.columns)}列"
                self.ui.label_info.setText(data_info)

                # 3. 添加数据加载完成的提示框
                QMessageBox.information(self, "加载成功",
                                        f"数据加载完成！\n共{len(self.df)}行 × {len(self.df.columns)}列")

                # 4. 启用保存按钮
                self.ui.btn_Save.setEnabled(True)

            except Exception as e:
                error_msg = f"加载数据失败：{str(e)}"
                QMessageBox.critical(self, "错误", error_msg)
                self.ui.label_info.setText(error_msg)
                self.ui.btn_Save.setEnabled(False)

    def on_Save(self):
        """触发数据保存（启动子线程）"""
        if self.df.empty:
            QMessageBox.warning(self, "警告", "无数据可保存！")
            return

        # 获取选择的文件格式
        format_text = self.ui.combo_Format.currentText()
        if "CSV" in format_text:
            file_format = "csv"
            file_filter = "CSV Files (*.csv)"
            file_ext = ".csv"
        else:
            file_format = "xlsx"
            file_filter = "Excel Files (*.xlsx)"
            file_ext = ".xlsx"

        # 选择保存路径
        filename, _ = QFileDialog.getSaveFileName(
            self,
            'Save File',
            os.path.expanduser("~") + "/Desktop",
            file_filter
        )

        if not filename:
            return  # 用户取消选择

        # 确保文件后缀正确
        if not filename.endswith(file_ext):
            filename += file_ext

        # 停止之前的线程（如果存在）
        if self.save_thread and self.save_thread.isRunning():
            self.save_thread.stop()
            self.save_thread.wait()

        # 创建并启动保存线程
        self.save_thread = SaveDataThread(self.df, filename, file_format, chunk_size=1000)
        # 绑定线程信号
        self.save_thread.progress_update.connect(self.ui.progressBar.setValue)
        self.save_thread.save_finished.connect(self.on_save_finished)

        # 禁用按钮，防止重复点击
        self.ui.btn_Save.setEnabled(False)
        self.ui.btn_Load.setEnabled(False)

        # 启动线程
        self.save_thread.start()

    def on_save_finished(self, success, message):
        """保存完成后的回调处理"""
        # 恢复按钮状态
        self.ui.btn_Save.setEnabled(True)
        self.ui.btn_Load.setEnabled(True)

        # 显示结果提示
        if success:
            QMessageBox.information(self, "保存结果", message)
        else:
            QMessageBox.critical(self, "保存结果", message)

        # 重置进度条
        self.ui.progressBar.setValue(0)

        # 释放线程资源
        self.save_thread = None

    def closeEvent(self, event):
        """窗口关闭时停止线程"""
        if self.save_thread and self.save_thread.isRunning():
            self.save_thread.stop()
            self.save_thread.wait()
        event.accept()