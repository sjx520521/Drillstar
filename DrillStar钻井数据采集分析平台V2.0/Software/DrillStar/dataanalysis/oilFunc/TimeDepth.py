import numpy as np
import pandas as pd
from PyQt5.QtCore import QAbstractTableModel, Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from dataanalysis.async_task import BusyTaskMixin


class PreviewModel(QAbstractTableModel):
    def __init__(self, df: pd.DataFrame):
        super().__init__()
        self.df = df

    def rowCount(self, parent=None):
        return len(self.df.index)

    def columnCount(self, parent=None):
        return len(self.df.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole:
            return None
        value = self.df.iat[index.row(), index.column()]
        if pd.isna(value):
            return ""
        if isinstance(value, (float, np.floating)):
            return f"{value:.4f}"
        return str(value)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return str(self.df.columns[section])
        return str(section + 1)


class Win_OilFuncTimeDepth(QWidget, BusyTaskMixin):
    def __init__(self, node: object):
        super().__init__()
        self.node = node
        setattr(node, "window", self)

        self.df_source = pd.DataFrame()
        self.df_output = pd.DataFrame()
        self.preview_model = None

        self.setWindowTitle("OilFunc [时深对标]")
        self.resize(980, 680)

        self._build_ui()
        self._bind_signals()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("时深对标")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        desc = QLabel(
            "该功能用于将时序采集数据映射为深度序列数据。系统可识别时间列和深度列，"
            "并按设定深度步长生成新的深度坐标结果。"
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        form = QFormLayout()
        self.cb_time = QComboBox()
        self.cb_depth = QComboBox()
        self.cb_method = QComboBox()
        self.cb_method.addItems(["最近值", "深度分箱均值", "深度分箱中值"])
        self.le_step = QLineEdit("0.1")
        self.le_step.setPlaceholderText("深度步长")
        form.addRow("时间列", self.cb_time)
        form.addRow("深度列", self.cb_depth)
        form.addRow("转换方式", self.cb_method)
        form.addRow("深度步长", self.le_step)
        layout.addLayout(form)

        button_row = QHBoxLayout()
        self.btn_load = QPushButton("Load")
        self.btn_convert = QPushButton("执行时深对标")
        self.btn_transfer = QPushButton("Transfer")
        button_row.addWidget(self.btn_load)
        button_row.addWidget(self.btn_convert)
        button_row.addWidget(self.btn_transfer)
        layout.addLayout(button_row)

        self.label_summary = QLabel("当前状态：未加载数据。")
        self.label_summary.setWordWrap(True)
        layout.addWidget(self.label_summary)

        self.table = QTableView()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.table)

    def _bind_signals(self):
        self.btn_load.clicked.connect(self.on_load)
        self.btn_convert.clicked.connect(self.on_convert)
        self.btn_transfer.clicked.connect(self.on_transfer)

    def _get_input_df(self) -> pd.DataFrame:
        input_node = self.node.getInput(0) if hasattr(self.node, "getInput") else None
        if input_node is None:
            return pd.DataFrame()
        result = input_node.serialize()
        if isinstance(result, dict):
            value = result.get("value", pd.DataFrame())
            return value.copy() if isinstance(value, pd.DataFrame) else pd.DataFrame()
        if isinstance(result, pd.DataFrame):
            return result.copy()
        return pd.DataFrame()

    def _auto_detect_column(self, keywords, numeric_only=False):
        if self.df_source.empty:
            return ""
        for col in self.df_source.columns:
            col_text = str(col).strip().lower()
            if any(keyword in col_text for keyword in keywords):
                if numeric_only and not pd.api.types.is_numeric_dtype(self.df_source[col]):
                    continue
                return col
        if numeric_only:
            numeric_cols = self.df_source.select_dtypes(include=[np.number]).columns.tolist()
            return numeric_cols[0] if numeric_cols else ""
        return self.df_source.columns[0] if len(self.df_source.columns) else ""

    def on_load(self):
        try:
            self.df_source = self._get_input_df()
            if self.df_source.empty:
                QMessageBox.warning(self, "提示", "上游节点没有可用数据。")
                return

            columns = [str(col) for col in self.df_source.columns]
            self.cb_time.clear()
            self.cb_depth.clear()
            self.cb_time.addItems(columns)
            self.cb_depth.addItems(columns)

            time_col = self._auto_detect_column(["time", "date", "timestamp", "时间", "日期"])
            depth_col = self._auto_detect_column(["depth", "md", "井深", "测深", "深度"], numeric_only=True)
            if time_col:
                self.cb_time.setCurrentText(str(time_col))
            if depth_col:
                self.cb_depth.setCurrentText(str(depth_col))

            self.label_summary.setText(
                f"当前状态：已加载 {self.df_source.shape[0]} 行 × {self.df_source.shape[1]} 列，"
                f"建议时间列为 {time_col or '未识别'}，建议深度列为 {depth_col or '未识别'}。"
            )
            QMessageBox.information(self, "成功", "时深对标数据已加载。")
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"加载失败：{exc}")

    def _convert_time_depth(self, time_col, depth_col, step, method):
        work_df = self.df_source.copy()
        work_df[time_col] = pd.to_datetime(work_df[time_col], errors="coerce")
        work_df[depth_col] = pd.to_numeric(work_df[depth_col], errors="coerce")
        work_df = work_df.dropna(subset=[time_col, depth_col]).sort_values(time_col)
        if work_df.empty:
            raise ValueError("时间列或深度列清洗后无有效数据。")

        work_df[depth_col] = work_df[depth_col].cummax()
        work_df = work_df.drop_duplicates(subset=[depth_col], keep="last").reset_index(drop=True)
        if work_df.empty:
            raise ValueError("深度列去重后无有效数据。")

        min_depth = float(work_df[depth_col].min())
        max_depth = float(work_df[depth_col].max())
        depth_grid = np.arange(min_depth, max_depth + step, step)

        if method == "最近值":
            source_depth = work_df[depth_col].to_numpy()
            output_df = pd.DataFrame({"深度": depth_grid})
            nearest_idx = np.searchsorted(source_depth, depth_grid, side="left")
            nearest_idx = np.clip(nearest_idx, 0, len(source_depth) - 1)
            for col in work_df.columns:
                if col == depth_col:
                    continue
                output_df[str(col)] = work_df.iloc[nearest_idx][col].to_numpy()
        else:
            bins = np.arange(min_depth, max_depth + step, step)
            grouped = work_df.copy()
            grouped["_depth_bin"] = pd.cut(grouped[depth_col], bins=bins, include_lowest=True)
            numeric_cols = work_df.select_dtypes(include=[np.number]).columns.tolist()
            if depth_col not in numeric_cols:
                numeric_cols.append(depth_col)
            agg_name = "mean" if method == "深度分箱均值" else "median"
            output_df = grouped.groupby("_depth_bin")[numeric_cols].agg(agg_name).reset_index(drop=True)
            output_df.insert(0, "深度", bins[:-1][: len(output_df)])
            output_df = output_df.drop(columns=[depth_col], errors="ignore")

        output_df = output_df.drop(columns=[time_col], errors="ignore").reset_index(drop=True)
        return output_df

    def on_convert(self):
        try:
            if self.df_source.empty:
                QMessageBox.warning(self, "提示", "请先加载数据。")
                return

            time_col = self.cb_time.currentText().strip()
            depth_col = self.cb_depth.currentText().strip()
            if not time_col or not depth_col:
                raise ValueError("请先选择时间列和深度列。")

            step = float(self.le_step.text().strip() or "0.1")
            if step <= 0:
                raise ValueError("深度步长必须大于 0。")

            self._start_background_task(
                "时深对标",
                "正在执行时深对标，请稍候...",
                self._convert_time_depth,
                self._on_convert_finished,
                self._on_convert_failed,
                time_col,
                depth_col,
                step,
                self.cb_method.currentText(),
            )
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"时深对标失败：{exc}")

    def _on_convert_finished(self, output_df):
        self.df_output = output_df
        self.preview_model = PreviewModel(self.df_output.head(1000))
        self.table.setModel(self.preview_model)
        self.label_summary.setText(
            f"当前状态：时深对标完成，输出 {self.df_output.shape[0]} 行 × {self.df_output.shape[1]} 列。"
        )
        QMessageBox.information(self, "成功", "时深对标已完成。")

    def _on_convert_failed(self, message):
        QMessageBox.critical(self, "错误", f"时深对标失败：{message}")

    def on_transfer(self):
        try:
            if self.df_output.empty:
                QMessageBox.warning(self, "提示", "当前没有可传递的结果。")
                return

            success = True
            if hasattr(self.node, "LoadData"):
                success = bool(self.node.LoadData(self.df_output))
            else:
                self.node.data = {"value": self.df_output}
            if not success:
                raise RuntimeError("结果传递失败。")

            if hasattr(self.node, "eval"):
                self.node.eval()
            if hasattr(self.node, "evalChildren"):
                self.node.evalChildren()

            QMessageBox.information(self, "成功", "时深对标结果已传递到下游节点。")
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"结果传递失败：{exc}")

    def closeEvent(self, event):
        self.hide()
        event.ignore()
