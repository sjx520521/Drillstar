import logging
from datetime import datetime

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt5.QtCore import QThread, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QGuiApplication
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from dataanalysis.ui.oilFuncStickSlip_ui import Ui_OilFuncStickSlip


logger = logging.getLogger(__name__)
pg.setConfigOptions(antialias=True, useOpenGL=False, enableExperimental=False)


class SSIWorker(QThread):
    finished_ok = pyqtSignal(object, object)
    failed = pyqtSignal(str)

    def __init__(self, df: pd.DataFrame, time_column: str, rpm_column: str):
        super().__init__()
        self.df = df.copy()
        self.time_column = time_column
        self.rpm_column = rpm_column

    def run(self):
        try:
            result_df, stats = self._calculate()
            self.finished_ok.emit(result_df, stats)
        except Exception as exc:
            self.failed.emit(str(exc))

    def _calculate(self):
        work_df = self.df[[self.time_column, self.rpm_column]].copy()
        work_df[self.time_column] = pd.to_datetime(work_df[self.time_column], errors="coerce")
        work_df[self.rpm_column] = pd.to_numeric(work_df[self.rpm_column], errors="coerce")
        work_df = work_df.dropna(subset=[self.time_column, self.rpm_column]).sort_values(self.time_column)
        if work_df.empty:
            raise ValueError("时间列或转速列中没有可用于计算的有效数据。")

        start_time = work_df[self.time_column].iloc[0]
        seconds_from_start = (work_df[self.time_column] - start_time).dt.total_seconds()
        bucket_index = (seconds_from_start // 10).astype(int)
        work_df["_window_time"] = start_time + pd.to_timedelta(bucket_index * 10, unit="s")

        rows = []
        level_count = {level: 0 for level in range(7)}

        for window_time, group in work_df.groupby("_window_time"):
            rpm = group[self.rpm_column]
            if rpm.empty:
                continue

            max_rpm = float(rpm.max())
            min_rpm = float(rpm.min())
            mean_rpm = float(rpm.mean())

            if abs(mean_rpm) < 1e-9:
                ssi_value = 0.0
                ssi_level = 0
            else:
                ssi_value = (max_rpm - min_rpm) / mean_rpm
                if ssi_value < 0:
                    ssi_level = 6
                elif ssi_value <= 0.4:
                    ssi_level = 0
                elif ssi_value <= 0.8:
                    ssi_level = 1
                elif ssi_value <= 1.2:
                    ssi_level = 2
                elif ssi_value <= 1.6:
                    ssi_level = 3
                elif ssi_value <= 2.0:
                    ssi_level = 4
                elif ssi_value <= 2.4:
                    ssi_level = 5
                else:
                    ssi_level = 6

            rows.append(
                {
                    "time_window": window_time,
                    "ssi_value": ssi_value,
                    "ssi_level": ssi_level,
                    "max_rpm": max_rpm,
                    "min_rpm": min_rpm,
                    "mean_rpm": mean_rpm,
                }
            )
            level_count[ssi_level] += 1

        result_df = pd.DataFrame(rows).sort_values("time_window").reset_index(drop=True)
        if result_df.empty:
            raise ValueError("按 10 秒窗口计算后没有得到有效的 SSI 结果。")

        return result_df, {"level_count": level_count}


class StickSlipDateAxis(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        labels = []
        for value in values:
            try:
                labels.append(datetime.fromtimestamp(value).strftime("%m-%d\n%H:%M:%S"))
            except Exception:
                labels.append("")
        return labels


class Win_OilFuncStickSlip(QWidget):
    plot_finished_signal = pyqtSignal(object)

    def __init__(self, node: object):
        super().__init__()
        self.ui = Ui_OilFuncStickSlip()
        self.ui.setupUi(self)
        self.setWindowTitle("OilFunc [粘滑分析]")
        self.node = node
        if hasattr(self.node, "window"):
            self.node.window = self

        self.df = pd.DataFrame()
        self.ssi_result = pd.DataFrame()
        self.time_column = None
        self.rpm_column = None
        self.time_series = None
        self.time_array = None
        self.calc_stats = None
        self.msg_box = None
        self.worker = None
        self.plot_widget = None
        self.linear_region = None

        self._init_ui()
        self._bind_signals()
        self.plot_finished_signal.connect(self._on_plot_finished)

    def _init_ui(self):
        self._set_standard_text()

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QFrame()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(5, 5, 5, 5)
        self.scroll_area.setWidget(self.scroll_widget)

        if hasattr(self.ui, "widget_plot_placeholder"):
            self.ui.widget_plot_placeholder.setParent(None)
        self.ui.verticalLayout_3.addWidget(self.scroll_area)

    def _bind_signals(self):
        self.ui.btn_Load.clicked.connect(self.on_Load)
        self.ui.btn_apply.clicked.connect(self.on_Calculate)

    def _set_standard_text(self):
        self.ui.label_standard.setText(
            """
<html><body style="line-height:1.55;">
<p><b>SSI计算公式：</b> SSI = (RPMmax - RPMmin) / RPMavg</p>
<p><b>SSI粘滑等级划分：</b></p>
<p>0.0 ≤ SSI ≤ 0.4：等级0，无或轻微粘滑</p>
<p>0.4 < SSI ≤ 0.8：等级1，轻度粘滑</p>
<p>0.8 < SSI ≤ 1.2：等级2，中度粘滑</p>
<p>1.2 < SSI ≤ 1.6：等级3，中重度粘滑</p>
<p>1.6 < SSI ≤ 2.0：等级4，重度粘滑</p>
<p>2.0 < SSI ≤ 2.4：等级5，非常重度粘滑</p>
<p>SSI > 2.4：等级6，极端粘滑</p>
</body></html>
            """.strip()
        )

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _parse_time_column(self):
        self.time_column = None
        self.time_series = None
        self.time_array = None
        keywords = ["time", "date", "datetime", "timestamp", "日期", "时间"]

        for col in self.df.columns:
            col_text = str(col).lower()
            if not any(keyword in col_text for keyword in keywords):
                continue
            try:
                candidate = pd.to_datetime(self.df[col], errors="raise")
                if candidate.notna().sum() < 2:
                    continue
                self.time_column = col
                self.time_series = candidate
                self.time_array = (candidate - candidate.iloc[0]).dt.total_seconds().to_numpy()
                return
            except Exception:
                continue

    def _parse_rpm_column(self):
        self.rpm_column = None
        keywords = ["rpm", "转速"]
        for col in self.df.columns:
            col_text = str(col).lower()
            if any(keyword in col_text for keyword in keywords) and pd.api.types.is_numeric_dtype(self.df[col]):
                self.rpm_column = col
                return

    def on_Load(self):
        try:
            if not hasattr(self.node, "getInput") or self.node.getInput(0) is None:
                QMessageBox.warning(self, "提示", "上游无数据。")
                return

            result = self.node.getInput(0).serialize()
            self.df = result["value"].copy() if isinstance(result, dict) and "value" in result else pd.DataFrame()
            if self.df.empty:
                QMessageBox.warning(self, "提示", "数据为空。")
                return

            self._parse_time_column()
            self._parse_rpm_column()

            self.ui.cB_WOB_2.clear()
            numeric_cols = [str(col) for col in self.df.columns if pd.api.types.is_numeric_dtype(self.df[col])]
            self.ui.cB_WOB_2.addItems(numeric_cols)
            if self.rpm_column is not None:
                self.ui.cB_WOB_2.setCurrentText(str(self.rpm_column))

            if self.time_column is None:
                QMessageBox.warning(self, "提示", "未检测到正确格式的时间列，请先使用时间转换功能。")
            else:
                QMessageBox.information(self, "成功", f"Load 数据成功：{self.df.shape}")
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"Load 失败：{exc}")
            logger.exception("StickSlip load failed")

    def on_Calculate(self):
        try:
            if self.df.empty:
                QMessageBox.warning(self, "提示", "请先 Load 数据。")
                return

            if not self.time_column or self.time_column not in self.df.columns:
                QMessageBox.warning(self, "提示", "未检测到正确格式的时间列，请先使用时间转换功能。")
                return

            selected_rpm = self.ui.cB_WOB_2.currentText().strip()
            if selected_rpm not in self.df.columns:
                QMessageBox.warning(self, "提示", "选中的转速列无效。")
                return

            self.msg_box = QMessageBox(self)
            self.msg_box.setWindowTitle("计算中")
            self.msg_box.setText("按10秒窗口计算SSI并绘图中...")
            self.msg_box.setStandardButtons(QMessageBox.NoButton)
            self.msg_box.setModal(False)
            self.msg_box.show()
            QGuiApplication.processEvents()

            self.worker = SSIWorker(self.df, self.time_column, selected_rpm)
            self.worker.finished_ok.connect(self.on_ssi_calculated)
            self.worker.failed.connect(self.on_ssi_error)
            self.worker.start()
            QTimer.singleShot(60000, self._close_msg_box)
        except Exception as exc:
            self._close_msg_box()
            QMessageBox.critical(self, "错误", f"计算失败：{exc}")

    def _close_msg_box(self):
        if self.msg_box is not None and self.msg_box.isVisible():
            self.msg_box.close()
            self.msg_box.deleteLater()
        self.msg_box = None

    def on_ssi_calculated(self, ssi_result, stats):
        self.ssi_result = ssi_result.copy()
        self.calc_stats = stats
        self._draw_ssi_plot()

    def on_ssi_error(self, error_msg):
        self._close_msg_box()
        QMessageBox.critical(self, "错误", f"SSI 计算失败：{error_msg}")

    def _draw_ssi_plot(self):
        try:
            self._clear_layout(self.scroll_layout)
            if self.ssi_result.empty:
                self._close_msg_box()
                QMessageBox.warning(self, "提示", "SSI 计算结果为空，无法绘图。")
                return

            plot_df = self.ssi_result.copy()
            plot_df["time_num"] = pd.to_datetime(plot_df["time_window"]).astype("int64") // 10**9
            time_data = plot_df["time_num"].to_numpy(dtype=float)
            ssi_data = plot_df["ssi_value"].to_numpy(dtype=float)
            level_data = plot_df["ssi_level"].to_numpy(dtype=float)

            normal_mask = level_data < 3
            high_mask = level_data >= 3

            self.plot_widget = pg.PlotWidget(axisItems={"bottom": StickSlipDateAxis(orientation="bottom")})
            self.plot_widget.setBackground("w")
            self.plot_widget.showGrid(x=True, y=True, alpha=0.35)
            self.plot_widget.setMinimumHeight(420)
            self.plot_widget.setLabel("left", "SSI")
            self.plot_widget.setLabel("bottom", "时间")
            legend = self.plot_widget.addLegend(offset=(10, 10))

            if normal_mask.any():
                normal_scatter = pg.ScatterPlotItem(
                    x=time_data[normal_mask],
                    y=ssi_data[normal_mask],
                    size=8,
                    pen=pg.mkPen(QColor(0, 122, 204), width=1.5),
                    brush=pg.mkBrush(QColor(0, 122, 204, 160)),
                )
                self.plot_widget.addItem(normal_scatter)
                legend.addItem(normal_scatter, "SSI 等级 < 3")

            if high_mask.any():
                high_scatter = pg.ScatterPlotItem(
                    x=time_data[high_mask],
                    y=ssi_data[high_mask],
                    size=10,
                    pen=pg.mkPen(QColor(220, 53, 69), width=1.5),
                    brush=pg.mkBrush(QColor(220, 53, 69, 170)),
                )
                self.plot_widget.addItem(high_scatter)
                legend.addItem(high_scatter, "SSI 等级 ≥ 3")

            min_time = float(time_data.min())
            max_time = float(time_data.max())
            default_right = min_time + max((max_time - min_time) * 0.1, 1.0)
            self.linear_region = pg.LinearRegionItem(
                [min_time, min(default_right, max_time)],
                pen=pg.mkPen(QColor(0, 0, 0), width=1.5),
                brush=pg.mkBrush(QColor(0, 0, 255, 30)),
                movable=True,
            )
            self.linear_region.sigRegionChanged.connect(self._on_region_changed)
            self.plot_widget.addItem(self.linear_region)

            self.scroll_layout.addWidget(self.plot_widget)
            self._update_time_range_label()
            self.plot_finished_signal.emit(self.calc_stats)
        except Exception as exc:
            self._close_msg_box()
            QMessageBox.critical(self, "错误", f"绘图失败：{exc}")

    def _on_region_changed(self):
        self._update_time_range_label()

    def _update_time_range_label(self):
        if self.ssi_result.empty or self.linear_region is None:
            self.ui.label_time_range.setText("当前选中时间：无")
            return

        min_time_num, max_time_num = self.linear_region.getRegion()
        time_values = pd.to_datetime(self.ssi_result["time_window"]).astype("int64") // 10**9
        start_idx = int(np.argmin(np.abs(time_values.to_numpy(dtype=float) - min_time_num)))
        end_idx = int(np.argmin(np.abs(time_values.to_numpy(dtype=float) - max_time_num)))
        start_time = pd.to_datetime(self.ssi_result["time_window"].iloc[start_idx])
        end_time = pd.to_datetime(self.ssi_result["time_window"].iloc[end_idx])
        self.ui.label_time_range.setText(
            f"当前选中时间：\n{start_time.strftime('%Y-%m-%d %H:%M:%S')}\n至\n{end_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )

    def _on_plot_finished(self, stats):
        self._close_msg_box()
        if not stats:
            return
        level_info = "\n".join(
            [f"等级 {level}：{count} 个点" for level, count in stats["level_count"].items() if count > 0]
        )
        if level_info:
            QMessageBox.information(self, "计算统计结果", level_info)


def create_stick_slip_window(node):
    return Win_OilFuncStickSlip(node)


_orig_stickslip_init_ui = Win_OilFuncStickSlip._init_ui


def _stickslip_init_ui_paste(self):
    _orig_stickslip_init_ui(self)
    self.setWindowTitle("OilFunc [粘滑分析]")
    self.ui.groupBox_2.setTitle("标准规范")
    self.ui.label_standard.setText(
        """
<html><body style="line-height:1.55;">
<p><b>SSI计算公式：</b> SSI = (RPMmax - RPMmin) / RPMavg</p>
<p><b>SSI粘滑等级划分：</b></p>
<p>0.0 ≤ SSI ≤ 0.4：粘滑等级为0，无或轻微粘滑</p>
<p>0.4 < SSI ≤ 0.8：粘滑等级为1，轻度粘滑</p>
<p>0.8 < SSI ≤ 1.2：粘滑等级为2，中度粘滑</p>
<p>1.2 < SSI ≤ 1.6：粘滑等级为3，中重度粘滑</p>
<p>1.6 < SSI ≤ 2.0：粘滑等级为4，重度粘滑</p>
<p>2.0 < SSI ≤ 2.4：粘滑等级为5，非常重度粘滑</p>
<p>SSI > 2.4：粘滑等级为6，极端粘滑</p>
</body></html>
        """.strip()
    )


Win_OilFuncStickSlip._init_ui = _stickslip_init_ui_paste


def _stickslip_standard_html(self):
    return """
<html>
<body style="line-height:1.5; margin:0; padding:0;">
<p style="margin:0; padding:0;"><b>SSI计算公式：</b> <span style="font-family:'Courier New', monospace; font-size:12pt;"><i>SSI</i> = (<i>RPM</i><sub>max</sub> - <i>RPM</i><sub>min</sub>) / <i>RPM</i><sub>avg</sub> × 100%</span></p>
<p style="margin:8px 0 5px 0; padding:0;"><b>SSI粘滑等级划分：</b></p>
<p style="margin:4px; padding:0;">0.0≤SSI≤0.4，粘滑等级为0，无或轻微粘滑</p>
<p style="margin:4px; padding:0;">0.4≤SSI≤0.8，粘滑等级为1，轻度粘滑</p>
<p style="margin:4px; padding:0;">0.8≤SSI≤1.2，粘滑等级为2，中度粘滑</p>
<p style="margin:4px; padding:0;">1.2≤SSI≤1.6，粘滑等级为3，中重度粘滑</p>
<p style="margin:4px; padding:0;">1.6≤SSI≤2.0，粘滑等级为4，重度粘滑</p>
<p style="margin:4px; padding:0;">2.0≤SSI≤2.4，粘滑等级为5，非常重度粘滑</p>
<p style="margin:4px; padding:0;">SSI≥2.4，粘滑等级为6，极端粘滑（可能卡钻）</p>
</body>
</html>
    """.strip()


def _stickslip_bind_signals(self):
    self.ui.btn_Load.clicked.connect(self.on_Load)
    self.ui.btn_apply.clicked.connect(self.on_Calculate)
    if hasattr(self.ui, "btn_Transfer"):
        self.ui.btn_Transfer.clicked.connect(self.on_Transfer)


def _stickslip_init_ui_v2(self):
    _orig_stickslip_init_ui(self)
    self.setWindowTitle("OilFunc [粘滑分析]")
    self.ui.groupBox_2.setTitle("标准规范")
    self.ui.label_standard.setText(self._standard_html())
    if hasattr(self.ui, "btn_Transfer"):
        self.ui.btn_Transfer.setText("Transfer")


def _stickslip_build_transfer_dataframe(self):
    if self.ssi_result.empty:
        return pd.DataFrame()

    output_df = self.ssi_result.copy()
    output_df["时间窗口"] = pd.to_datetime(output_df["time_window"], errors="coerce")
    output_df["SSI"] = pd.to_numeric(output_df["ssi_value"], errors="coerce")
    output_df["粘滑等级"] = pd.to_numeric(output_df["ssi_level"], errors="coerce").astype("Int64")
    output_df["最大转速"] = pd.to_numeric(output_df["max_rpm"], errors="coerce")
    output_df["最小转速"] = pd.to_numeric(output_df["min_rpm"], errors="coerce")
    output_df["平均转速"] = pd.to_numeric(output_df["mean_rpm"], errors="coerce")
    return output_df[
        [
            "时间窗口",
            "SSI",
            "粘滑等级",
            "最大转速",
            "最小转速",
            "平均转速",
            "time_window",
            "ssi_value",
            "ssi_level",
            "max_rpm",
            "min_rpm",
            "mean_rpm",
        ]
    ]


def _stickslip_on_transfer(self):
    try:
        output_df = self._build_transfer_dataframe()
        if output_df.empty:
            QMessageBox.warning(self, "提示", "请先完成粘滑分析。")
            return

        success = True
        if hasattr(self.node, "LoadData"):
            success = bool(self.node.LoadData(output_df))
        else:
            self.node.data = {"value": output_df}

        if not success:
            QMessageBox.critical(self, "错误", "结果传递失败。")
            return

        if hasattr(self.node, "eval"):
            self.node.eval()
        if hasattr(self.node, "evalChildren"):
            self.node.evalChildren()

        QMessageBox.information(self, "成功", f"结果已传递：{output_df.shape}")
    except Exception as exc:
        QMessageBox.critical(self, "错误", f"结果传递失败：{exc}")


Win_OilFuncStickSlip._standard_html = _stickslip_standard_html
Win_OilFuncStickSlip._bind_signals = _stickslip_bind_signals
Win_OilFuncStickSlip._init_ui = _stickslip_init_ui_v2
Win_OilFuncStickSlip._build_transfer_dataframe = _stickslip_build_transfer_dataframe
Win_OilFuncStickSlip.on_Transfer = _stickslip_on_transfer


def _stickslip_standard_html_v2(self):
    full_text = """
            <html>
            <body style="line-height:1.5; margin:0; padding:0;">
            <p style="margin:0; padding:0;"><b>SSI计算公式：</b>   <span style="font-family:'Courier New', monospace;font-size:12pt;"><i>SSI</i> = (<i>RPM</i><sub>max</sub> - <i>RPM</i><sub>min</sub>) / <i>RPM</i><sub>avg</sub> × 100%</span></p>
            <p style="margin:8px 0 5px 0; padding:0;"><b>SSI黏滑等级划分：</b></p>
            <p style="margin:4px; padding:0;">0.0≤SSI≤0.4,黏滑等级为0,无或轻微粘滑</p>
            <p style="margin:4px; padding:0;">0.4≤SSI≤0.8,黏滑等级为1,轻度粘滑</p>
            <p style="margin:4px; padding:0;">0.8≤SSI≤1.2,黏滑等级为2,中度粘滑</p>
            <p style="margin:4px; padding:0;">1.2≤SSI≤1.6,黏滑等级为3,中重度粘滑</p>
            <p style="margin:4px; padding:0;">1.6≤SSI≤2.0,黏滑等级为4,重度粘滑</p>
            <p style="margin:4px; padding:0;">2.0≤SSI≤2.4,黏滑等级为5,非常重度粘滑</p>
            <p style="margin:4px; padding:0;">SSI≥2.4,黏滑等级为6,极端粘滑(可能卡钻)</p>
            </body>
            </html>
            """
    return full_text.strip()


_orig_stickslip_on_plot_finished = Win_OilFuncStickSlip._on_plot_finished


def _stickslip_on_plot_finished_v2(self, stats):
    _orig_stickslip_on_plot_finished(self, stats)
    if hasattr(self.node, "markValid"):
        self.node.markValid()
    if hasattr(self.node, "markDirty"):
        self.node.markDirty(False)
    if hasattr(self.node, "markInvalid"):
        self.node.markInvalid(False)


def _stickslip_on_transfer_v2(self):
    try:
        output_df = self._build_transfer_dataframe()
        if output_df.empty:
            QMessageBox.warning(self, "提示", "请先完成粘滑分析。")
            return

        success = True
        if hasattr(self.node, "LoadData"):
            success = bool(self.node.LoadData(output_df))
        else:
            self.node.data = {"value": output_df}

        if not success:
            QMessageBox.critical(self, "错误", "结果传递失败。")
            return

        if hasattr(self.node, "markValid"):
            self.node.markValid()
        if hasattr(self.node, "markDirty"):
            self.node.markDirty(False)
        if hasattr(self.node, "markInvalid"):
            self.node.markInvalid(False)
        if hasattr(self.node, "eval"):
            self.node.eval()
        if hasattr(self.node, "evalChildren"):
            self.node.evalChildren()

        QMessageBox.information(self, "成功", f"结果已传递：{output_df.shape}")
    except Exception as exc:
        QMessageBox.critical(self, "错误", f"结果传递失败：{exc}")


Win_OilFuncStickSlip._standard_html = _stickslip_standard_html_v2
Win_OilFuncStickSlip._on_plot_finished = _stickslip_on_plot_finished_v2
Win_OilFuncStickSlip.on_Transfer = _stickslip_on_transfer_v2
