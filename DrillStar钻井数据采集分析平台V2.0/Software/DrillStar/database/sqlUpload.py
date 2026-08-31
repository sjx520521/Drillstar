import os
import re
import pandas as pd
import pymysql
from threading import Thread
from PyQt5.QtWidgets import QWidget, QFileDialog, QMessageBox
from PyQt5.QtCore import pyqtSignal, QThread, Qt, QCoreApplication, QMetaObject, Q_ARG, QObject


# 解决子线程中无法操作UI的问题：定义全局信号
class UISignal(QObject):
    show_msg = pyqtSignal(str, str)  # 消息内容、类型（info/warning/error）
    update_progress = pyqtSignal(int)


ui_signal = UISignal()


def detect_encoding(filepath):
    """优化的自动检测文件编码（增加重试、扩大检测范围、优先常用编码）"""
    # 定义优先检测的编码列表（覆盖99%的中文场景）
    candidate_encodings = ['gbk', 'gb18030', 'utf-8-sig', 'utf-8', 'gb2312', 'latin-1']

    try:
        import chardet
        # 读取更多数据提高检测准确率（读取整个文件的前50000字节，或全部内容）
        with open(filepath, 'rb') as f:
            # 读取最多50000字节，避免大文件占用过多内存
            raw_data = f.read(50000) or f.read()  # 若前50000字节为空，读取全部
            if not raw_data:
                return 'utf-8-sig'  # 空文件默认utf-8-sig

            # chardet检测
            result = chardet.detect(raw_data)
            detected_encoding = result['encoding']
            confidence = result['confidence']  # 检测置信度

            # 置信度>0.7时使用检测结果，否则用候选列表
            if detected_encoding and confidence > 0.7:
                detected_encoding = detected_encoding.lower()
                # 映射到标准编码名
                if detected_encoding in ['gb2312', 'gbk', 'gb18030']:
                    return 'gb18030'  # gb18030兼容gbk/gb2312
                elif detected_encoding in ['utf-8', 'utf-8-sig']:
                    return 'utf-8-sig'
                else:
                    return detected_encoding
            else:
                # 置信度低，返回候选列表第一个（优先gb18030）
                return 'gb18030'
    except ImportError:
        # 未安装chardet时，直接按候选列表重试
        return 'gb18030'
    except Exception:
        # 任何异常默认返回gb18030（兼容所有中文编码）
        return 'gb18030'


class CSVLoadThread(QThread):
    load_finished = pyqtSignal(pd.DataFrame)
    load_failed = pyqtSignal(str)

    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath

    def run(self):
        try:
            file_ext = os.path.splitext(self.filepath)[-1].lower()
            # 获取候选编码列表（优先检测的编码）
            candidate_encodings = ['gb18030', 'utf-8-sig', 'utf-8', 'gbk', 'gb2312']
            df = None

            # 编码重试机制：逐个尝试编码，直到成功
            for encoding in candidate_encodings:
                try:
                    if file_ext == ".csv":
                        # 强制将所有列转为字符串，避免类型转换问题
                        df = pd.read_csv(
                            self.filepath,
                            encoding=encoding,
                            dtype=str,
                            on_bad_lines='skip'  # 跳过损坏的行（可选）
                        ).fillna('')
                    elif file_ext == '.xlsx':
                        df = pd.read_excel(self.filepath, dtype=str).fillna('')
                    else:
                        self.load_failed.emit("文件格式错误，仅支持CSV/XLSX")
                        return
                    # 读取成功则跳出循环
                    break
                except UnicodeDecodeError:
                    # 该编码失败，尝试下一个
                    continue
                except Exception as e:
                    # 非编码错误，直接抛出
                    raise e

            # 所有编码都尝试失败
            if df is None:
                self.load_failed.emit(f"所有编码尝试失败，无法读取文件")
                return

            self.load_finished.emit(df)
        except Exception as e:
            self.load_failed.emit(f"文件加载失败：{str(e)}")


class Win_SQlupload(QWidget):
    msg_Signal = pyqtSignal(str, int)
    progress_Signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        from database.ui.sqlUpload_ui import Ui_sqlUpload
        from database.share_DataBase import ShareInfo
        self.ShareInfo = ShareInfo
        self.ui = Ui_sqlUpload()
        self.ui.setupUi(self)
        self.filepath = None
        self.df = None
        self.load_thread = None

        # 初始化UI
        self.ui.progressBar.setRange(0, 100)
        self.ui.progressBar.setValue(0)
        self.ui.btn_Upload.setEnabled(False)

        # 信号连接
        self.ui.btn_OpenFile.clicked.connect(self.on_OpenFile)
        self.ui.btn_Upload.clicked.connect(self.on_UploadClicked)
        self.progress_Signal.connect(self.ui.progressBar.setValue, Qt.QueuedConnection)
        # 绑定全局UI信号
        ui_signal.show_msg.connect(self._show_message)
        ui_signal.update_progress.connect(self.ui.progressBar.setValue)

    def _show_message(self, msg, msg_type):
        """主线程中显示消息框"""
        if msg_type == "error":
            QMessageBox.critical(self, "错误", msg)
        elif msg_type == "warning":
            QMessageBox.warning(self, "警告", msg)
        else:
            QMessageBox.information(self, "信息", msg)

    def on_OpenFile(self):
        self.ui.lE_FilePath.clear()
        self.ui.progressBar.setValue(0)
        self.ui.btn_Upload.setEnabled(False)

        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "选择需要导入的文件",
            os.path.expanduser("~"),
            "CSV Files (*.csv);;Excel Files (*.xlsx);;All Files (*.*)"
        )

        if not filepath:
            self.msg_Signal.emit("---->未选择文件", 0)
            print("---->已选择文件：")
            return

        self.filepath = filepath
        self.ui.lE_FilePath.setText(filepath)
        self.msg_Signal.emit(f"---->已选择文件：{filepath}", 0)

        # 启动加载线程
        self.load_thread = CSVLoadThread(filepath)
        self.load_thread.load_finished.connect(self.on_file_loaded)
        self.load_thread.load_failed.connect(self.on_file_load_failed)
        self.load_thread.start()

    def on_file_loaded(self, df: pd.DataFrame):
        self.df = df
        self.df = self._handle_duplicate_columns(self.df)
        self.ui.btn_Upload.setEnabled(True)
        self.msg_Signal.emit(f"---->文件加载成功，共{len(df)}行{df.shape[1]}列", 0)

    def on_file_load_failed(self, error: str):
        err_msg = f"---->文件加载失败：{error}"
        self.msg_Signal.emit(err_msg, 1)

    def _handle_duplicate_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """处理重复列名，清理特殊字符"""
        cols = df.columns.tolist()
        new_cols = []
        col_count = {}

        for col in cols:
            # 保留中文列名（仅清理特殊符号）
            sanitized_col = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9_]', '_', str(col))
            if sanitized_col in col_count:
                col_count[sanitized_col] += 1
                new_col = f"{sanitized_col}_{col_count[sanitized_col]}"
            else:
                col_count[sanitized_col] = 0
                new_col = sanitized_col
            new_cols.append(new_col)

        df.columns = new_cols
        if 'id' in df.columns:
            df = df.drop(columns=['id'])
        return df

    def on_UploadClicked(self):
        """启动上传线程，避免UI阻塞"""
        upload_thread = Thread(target=self.on_UploadFile)
        upload_thread.daemon = True
        upload_thread.start()

    def on_UploadFile(self):
        """核心上传逻辑（子线程中执行，不直接操作UI）"""
        if self.ShareInfo.sql_cfg == {}:
            ui_signal.show_msg.emit("未连接数据库！", "error")
            self.msg_Signal.emit("---->未连接数据库！", 1)
            return

        if self.df is None or self.df.empty:
            ui_signal.show_msg.emit("无有效数据可上传！", "warning")
            self.msg_Signal.emit("---->无有效数据可上传！", 1)
            return

        conn = None
        cur = None
        try:
            conn = self.ShareInfo.DBconnect()
            if conn is None:
                ui_signal.show_msg.emit("数据库连接失败！", "error")
                return

            cur = conn.cursor()
            conn.autocommit = False

            # 1. 处理表名
            tablename = self.ui.lE_TableName.text().strip()
            if not tablename:
                ui_signal.show_msg.emit("表名不能为空！", "error")
                return

            if re.match(r"^[0-9]*$", tablename):
                ui_signal.show_msg.emit("表名不能为纯数字！", "error")
                return

            # 保留中文表名（仅清理特殊符号）
            tablename = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9_]', '_', tablename)

            # 2. 检查表是否存在
            cur.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = %s AND table_name = %s",
                (self.ShareInfo.sql_cfg['DB'], tablename)
            )
            if cur.fetchone():
                ui_signal.show_msg.emit("表名存在，请更改表名！", "error")
                return

            # 3. 构建列定义
            header = self.df.columns.tolist()
            KEY = []
            HEADER = []

            for item in header:
                dtype = str(self.df[item].dtype)
                if dtype in self.ShareInfo.KEYS_TYPE:
                    col_type = self.ShareInfo.KEYS_TYPE[dtype]
                    # 强制为字符串类型添加utf8mb4字符集
                    if col_type.startswith('VARCHAR'):
                        col_def = f"`{item}` {col_type} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                    else:
                        col_def = f"`{item}` {col_type}"
                    KEY.append(col_def)
                    HEADER.append(f"`{item}`")
                else:
                    ui_signal.show_msg.emit(f"列{item}的类型{dtype}不支持！", "error")
                    return

            if not KEY:
                ui_signal.show_msg.emit("无有效列可创建表！", "error")
                return

            # 4. 建表（强制utf8mb4）
            create_sql = f"""
            CREATE TABLE IF NOT EXISTS `{tablename}` (
                `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
                {','.join(KEY)}
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            cur.execute(create_sql)

            # 5. 批量插入（小批量+实时提交）
            batch_size = 50  # 进一步减小分块大小
            values = self.df.values.tolist()
            total_rows = len(values)
            insert_sql = f"INSERT INTO `{tablename}` ({','.join(HEADER)}) VALUES ({','.join(['%s'] * len(header))})"

            # 初始化进度
            ui_signal.update_progress.emit(0)
            success_rows = 0

            for i in range(0, total_rows, batch_size):
                batch = values[i:i + batch_size]
                # 强制将所有值转为字符串，避免编码问题
                batch = [[str(val) for val in row] for row in batch]
                cur.executemany(insert_sql, batch)
                success_rows += len(batch)
                # 更新进度
                progress = min(int(success_rows / total_rows * 100), 100)
                ui_signal.update_progress.emit(progress)
                # 每批提交一次，避免事务过大
                conn.commit()

            # 最终提交
            conn.commit()
            ui_signal.update_progress.emit(100)
            ui_signal.show_msg.emit(f"{tablename} 上传成功！共插入{success_rows}行数据", "info")
            self.msg_Signal.emit(f"---->上传完成！共插入{success_rows}行数据", 0)

        except Exception as e:
            err_msg = f"上传错误：{str(e)}"
            print(err_msg)
            self.msg_Signal.emit(err_msg, 1)
            ui_signal.show_msg.emit(err_msg, "error")
            if conn:
                conn.rollback()
        finally:
            # 确保资源释放
            if cur:
                cur.close()
            if conn:
                conn.close()
            # 重置进度条
            QMetaObject.invokeMethod(self.ui.progressBar, "setValue", Qt.QueuedConnection, Q_ARG(int, 100))


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    win = Win_SQlupload()
    win.show()
    sys.exit(app.exec_())