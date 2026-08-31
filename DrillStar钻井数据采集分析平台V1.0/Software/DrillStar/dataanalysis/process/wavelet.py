import math as m

import numpy as np
import pandas as pd
import pyqtgraph as pg
import pywt
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QMessageBox, QWidget

from dataanalysis.buttonNode import ButtonNode
from dataanalysis.ui.ProcessWavelet_ui import Ui_wavelet


def _process_wavelet_coeffs(coeffs, lamda_mode, option, threshold_ratio, substitute, data_length, level):
    if lamda_mode == "median_cA":
        sigma = np.median(np.abs(coeffs[0])) / 0.6745
        threshold = sigma * m.sqrt(2 * m.log10(data_length))
        lamda = threshold / (m.log(m.e + 2 * (len(coeffs[0]) - 1)))
        coeffs[0] = pywt.threshold(
            data=coeffs[0],
            value=lamda,
            mode=option,
            substitute=substitute,
        )
        return coeffs

    if lamda_mode == "median_cD":
        sigma = np.median(np.abs(coeffs[-1])) / 0.6745
        lamda = sigma * m.sqrt(2.0 * m.log(data_length))
        alpha = 0.1

        for index in range(1, len(coeffs)):
            coeff = np.asarray(coeffs[index], dtype=float)
            abs_coeff = np.abs(coeff)
            mask = abs_coeff >= lamda
            coeff[mask] = np.sign(coeff[mask]) * (abs_coeff[mask] - alpha * lamda)
            coeff[~mask] = 0.0
            coeffs[index] = coeff
        return coeffs

    if lamda_mode == "median_cD_adaption":
        sigma = np.median(np.abs(coeffs[-1])) / 0.6745
        lamda = sigma * m.sqrt(2.0 * m.log(data_length))
        level_count = max(level, 1)

        for index in range(1, len(coeffs)):
            current_lamda = lamda / np.log2(level_count + 1)
            coeffs[index] = pywt.threshold(
                data=coeffs[index],
                value=current_lamda,
                mode=option,
            )
            level_count = max(level_count - 1, 1)
        return coeffs

    for index in range(1, len(coeffs)):
        coeff = np.asarray(coeffs[index], dtype=float)
        scale = float(np.max(np.abs(coeff))) if coeff.size else 0.0
        if scale <= 0:
            continue
        coeffs[index] = pywt.threshold(
            data=coeff,
            value=threshold_ratio * scale,
            mode=option,
            substitute=substitute,
        )
    return coeffs


class WaveletThread(QThread):
    finished_ok = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, action, signal_data, wavelet_name, mode, level, lamda_mode, option, threshold_ratio, substitute):
        super().__init__()
        self.action = action
        self.signal_data = np.asarray(signal_data, dtype=float)
        self.wavelet_name = wavelet_name
        self.mode = mode
        self.level = level
        self.lamda_mode = lamda_mode
        self.option = option
        self.threshold_ratio = threshold_ratio
        self.substitute = substitute

    def run(self):
        try:
            wavelet = pywt.Wavelet(self.wavelet_name)
            coeffs = pywt.wavedec(
                self.signal_data,
                wavelet=wavelet,
                mode=self.mode,
                level=self.level,
            )

            result = {
                "action": self.action,
                "coeffs": coeffs,
                "level": self.level,
            }

            if self.action == "denoise":
                coeffs = _process_wavelet_coeffs(
                    coeffs=coeffs,
                    lamda_mode=self.lamda_mode,
                    option=self.option,
                    threshold_ratio=self.threshold_ratio,
                    substitute=self.substitute,
                    data_length=len(self.signal_data),
                    level=self.level,
                )
                newdata = pywt.waverec(coeffs, wavelet=wavelet, mode=self.mode)
                result["coeffs"] = coeffs
                result["newdata"] = np.asarray(newdata[: len(self.signal_data)], dtype=float)

            self.finished_ok.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class Win_ProcessWavelet(QWidget):
    """小波分析节点窗口。"""

    def __init__(self, node: ButtonNode):
        super().__init__()
        self.ui = Ui_wavelet()
        self.ui.setupUi(self)
        self.setWindowTitle("数据分析 [小波分析]")

        self.node = node
        self.df = pd.DataFrame()
        self.df_result = pd.DataFrame()
        self.numeric_columns = []
        self.selected_column = ""

        self.signal_series = pd.Series(dtype=float)
        self.y = np.array([], dtype=float)
        self.newdata = np.array([], dtype=float)
        self.coeffs = None
        self.worker = None
        self._busy = False

        self.N = 0
        self.fs = 1000.0
        self.T = 1.0 / self.fs
        self.wavelet = None
        self.level = 0
        self.mode = ""
        self.option = ""
        self.lamda_mode = "default"

        self._init_ui()
        self._bind_events()

    def _init_ui(self):
        self.ui.btn_Load_2.setText("Load")
        self.ui.btn_analyze.setText("分解")
        self.ui.btn_Transfer.setText("Transfer")
        self.ui.btn_close.hide()
        self.ui.LE_size.setReadOnly(True)
        self.ui.LE_size.setText("0")
        self.ui.LE_value.setText("0.08")
        self.ui.LE_substitute.setText("0")

        self.ui.comb_column.clear()
        self.ui.comb_families.clear()
        self.ui.comb_family.clear()
        self.ui.comb_Level.clear()
        self.ui.comb_modes.clear()
        self.ui.comb_opt.clear()
        self.ui.combo_value.clear()

        self.ui.comb_families.addItems(pywt.families())
        self.ui.comb_modes.addItems(list(pywt.Modes.modes))
        self.ui.comb_opt.addItems(["soft", "hard", "greater", "less", "garrote"])
        self.ui.combo_value.addItems(["default", "median_cA", "median_cD", "median_cD_adaption"])

        if self.ui.comb_modes.count() > 2:
            self.ui.comb_modes.setCurrentIndex(2)

        self.mode = self.ui.comb_modes.currentText()
        self.option = self.ui.comb_opt.currentText()
        self.lamda_mode = self.ui.combo_value.currentText()

        self.win = pg.GraphicsLayoutWidget()
        self.win.setBackground("w")
        self.ui.verticalLayout.addWidget(self.win)

        self.on_family(self.ui.comb_families.currentText())
        self._refresh_status_text()
        self._update_action_state()

    def _bind_events(self):
        self.ui.btn_Load_2.clicked.connect(self.on_Load)
        self.ui.btn_analyze.clicked.connect(self.my_wt)
        self.ui.btn_denoiser.clicked.connect(self.wt_denoiser)
        self.ui.btn_overlap.clicked.connect(self.on_overlap)
        self.ui.btn_Transfer.clicked.connect(self.on_Transfer)

        self.ui.comb_column.currentTextChanged.connect(self.on_column_change)
        self.ui.comb_families.currentTextChanged.connect(self.on_family)
        self.ui.comb_family.currentTextChanged.connect(self.on_level)
        self.ui.comb_modes.currentTextChanged.connect(self.on_mode_change)
        self.ui.comb_opt.currentTextChanged.connect(self.on_opt_change)
        self.ui.combo_value.currentTextChanged.connect(self.on_lamda_mode_change)

    def _update_action_state(self):
        has_signal = self.N > 0 and self.wavelet is not None and self.ui.comb_Level.count() > 0
        has_result = self.newdata.size > 0 and not self.df_result.empty

        self.ui.btn_Load_2.setEnabled(not self._busy)
        self.ui.comb_column.setEnabled(not self._busy)
        self.ui.comb_families.setEnabled(not self._busy)
        self.ui.comb_family.setEnabled(not self._busy)
        self.ui.comb_Level.setEnabled(not self._busy)
        self.ui.comb_modes.setEnabled(not self._busy)
        self.ui.comb_opt.setEnabled(not self._busy)
        self.ui.combo_value.setEnabled(not self._busy)

        self.ui.btn_analyze.setEnabled(has_signal and not self._busy)
        self.ui.btn_denoiser.setEnabled(has_signal and not self._busy)
        self.ui.btn_overlap.setEnabled(has_result and not self._busy)
        self.ui.btn_Transfer.setEnabled(has_result and not self._busy)

    def _set_busy(self, busy, action_text=""):
        self._busy = busy
        if busy and action_text:
            self._refresh_status_text([f"正在执行：{action_text}"])
        else:
            self._refresh_status_text()
        self._update_action_state()

    def _refresh_status_text(self, extra_lines=None):
        lines = []

        if self.selected_column:
            lines.append(f"信号列：{self.selected_column}")
            lines.append(f"数据点数：{self.N}")
        else:
            lines.append("请先加载包含数值列的数据。")

        if self.wavelet is not None:
            lines.append(f"小波基：{self.wavelet.name}")

        if self.ui.comb_Level.count() > 0:
            lines.append(f"最大分解层数：{self.ui.comb_Level.count()}")

        if extra_lines:
            lines.extend(extra_lines)

        self.ui.textBrowser.clear()
        self.ui.textBrowser.setPlainText("\n".join(lines))

    def _safe_float(self, widget, default_value):
        text = widget.text().strip()
        if not text:
            return default_value
        try:
            return float(text)
        except ValueError:
            widget.setText(str(default_value))
            return default_value

    def _get_numeric_columns(self):
        numeric_columns = []
        for column in self.df.columns:
            series = pd.to_numeric(self.df[column], errors="coerce")
            if series.notna().sum() >= 2:
                numeric_columns.append(column)
        return numeric_columns

    def _preferred_column_index(self):
        if not self.numeric_columns:
            return -1

        time_keywords = ("time", "date", "datetime", "timestamp", "时间", "日期")
        for index, column in enumerate(self.numeric_columns):
            name = str(column).lower()
            if not any(keyword in name for keyword in time_keywords):
                return index
        return 0

    def _prepare_signal(self, column_name):
        series = pd.to_numeric(self.df[column_name], errors="coerce")
        if series.notna().sum() < 2:
            raise ValueError("所选列有效数值点不足，无法进行小波分析。")

        series = series.astype(float)
        series = series.interpolate(limit_direction="both").ffill().bfill()
        return series

    def on_Load(self):
        input_node = self.node.getInput(0)
        if input_node is None:
            self.node.markDirty()
            self.node.markInvalid()
            QMessageBox.warning(self, "警告", "上游节点无数据输入！")
            return

        try:
            result = input_node.serialize()
            self.df = result.get("value", pd.DataFrame())
            self.df_result = pd.DataFrame()
            self.newdata = np.array([], dtype=float)
            self.coeffs = None

            if not isinstance(self.df, pd.DataFrame) or self.df.empty:
                self.node.markInvalid()
                QMessageBox.warning(self, "警告", "加载的数据为空！")
                return

            self.numeric_columns = self._get_numeric_columns()
            self.ui.comb_column.clear()

            if not self.numeric_columns:
                self.selected_column = ""
                self.signal_series = pd.Series(dtype=float)
                self.y = np.array([], dtype=float)
                self.N = 0
                self.wavelet = None
                self.ui.comb_family.clear()
                self.ui.comb_Level.clear()
                self.ui.LE_size.setText("0")
                self.win.clear()
                self._refresh_status_text(["未检测到可分析的数值列。"])
                self._update_action_state()
                QMessageBox.warning(self, "警告", "数据中无可用于小波分析的数值列！")
                return

            self.ui.comb_column.addItems([str(column) for column in self.numeric_columns])
            preferred_index = self._preferred_column_index()
            self.ui.comb_column.setCurrentIndex(preferred_index)
            self.on_column_change(self.ui.comb_column.currentText())

            self.node.markValid()
            QMessageBox.information(
                self,
                "成功",
                f"数据加载完成：共{len(self.df)}行 x {len(self.df.columns)}列，可分析数值列{len(self.numeric_columns)}个。"
            )
        except Exception as exc:
            self.node.markInvalid()
            QMessageBox.critical(self, "错误", f"加载数据失败：{exc}")

    def on_column_change(self, column_name):
        if not column_name or self.df.empty:
            return

        self.selected_column = column_name
        self.newdata = np.array([], dtype=float)
        self.df_result = pd.DataFrame()
        self.coeffs = None
        self.win.clear()

        try:
            self.signal_series = self._prepare_signal(column_name)
            self.y = self.signal_series.to_numpy(dtype=float)
            self.N = len(self.y)
            self.T = 1.0 / self.fs
            self.ui.LE_size.setText(str(self.N))

            self.on_family(self.ui.comb_families.currentText())
            self._refresh_status_text()
        except Exception as exc:
            self.signal_series = pd.Series(dtype=float)
            self.y = np.array([], dtype=float)
            self.N = 0
            self.ui.LE_size.setText("0")
            self.ui.comb_Level.clear()
            self.wavelet = None
            self._refresh_status_text([f"当前列不可分析：{exc}"])

        self._update_action_state()

    def on_family(self, family):
        self.ui.comb_family.blockSignals(True)
        self.ui.comb_family.clear()
        if family:
            self.ui.comb_family.addItems(pywt.wavelist(family))
        self.ui.comb_family.blockSignals(False)

        if self.ui.comb_family.count() > 0:
            self.on_level(self.ui.comb_family.currentText())
        else:
            self.wavelet = None
            self.ui.comb_Level.clear()
            self._refresh_status_text()
            self._update_action_state()

    def on_level(self, wavelet_name):
        self.ui.comb_Level.clear()

        if not wavelet_name:
            self.wavelet = None
            self._refresh_status_text()
            self._update_action_state()
            return

        try:
            self.wavelet = pywt.Wavelet(wavelet_name)
            if self.N <= 0:
                self._refresh_status_text(["请先加载数据并选择信号列。"])
                self._update_action_state()
                return

            max_level = pywt.dwt_max_level(self.N, self.wavelet.dec_len)
            if max_level < 1:
                self._refresh_status_text(["当前信号长度不足，无法进行分解。"])
                self._update_action_state()
                return

            self.ui.comb_Level.addItems([str(i) for i in range(1, max_level + 1)])
            self._refresh_status_text()
        except Exception as exc:
            self.wavelet = None
            self._refresh_status_text([f"小波基加载失败：{exc}"])

        self._update_action_state()

    def on_mode_change(self, mode):
        self.mode = mode

    def on_opt_change(self, option):
        self.option = option

    def on_lamda_mode_change(self, mode):
        self.lamda_mode = mode
        is_default = mode == "default"
        self.ui.LE_value.setVisible(is_default)
        self.ui.LE_substitute.setVisible(is_default)

    def _require_ready_signal(self):
        if self.y.size == 0:
            QMessageBox.warning(self, "警告", "请先加载数据并选择数值列！")
            return False

        if self.wavelet is None:
            QMessageBox.warning(self, "警告", "请先选择小波基！")
            return False

        if self.ui.comb_Level.count() == 0:
            QMessageBox.warning(self, "警告", "当前数据长度不足，无法进行小波分解。")
            return False

        return True

    def _current_level(self):
        return int(self.ui.comb_Level.currentText())

    def _plot_decomposition(self):
        self.win.clear()
        for index, coeff in enumerate(self.coeffs):
            title = f"A{self.level}" if index == 0 else f"D{self.level - index + 1}"
            plot_item = self.win.addPlot(title=title)
            plot_item.showGrid(x=True, y=True)
            x_data, y_data = self._downsample_for_plot(coeff)
            plot_item.plot(x_data, y_data, pen=pg.mkPen("#1f77b4", width=1.5))
            self.win.nextRow()

    def _plot_denoise_result(self):
        self.win.clear()

        plot_original = self.win.addPlot(title="原始与去噪对比")
        plot_original.showGrid(x=True, y=True)
        plot_original.addLegend()
        x1, y1 = self._downsample_for_plot(self.y)
        x2, y2 = self._downsample_for_plot(self.newdata)
        plot_original.plot(x1, y1, pen=pg.mkPen("#1f77b4", width=1.3), name="Original")
        plot_original.plot(x2, y2, pen=pg.mkPen("#d62728", width=1.5), name="Denoised")
        self.win.nextRow()

        plot_result = self.win.addPlot(title="去噪结果")
        plot_result.showGrid(x=True, y=True)
        plot_result.plot(x2, y2, pen=pg.mkPen("#d62728", width=1.5))

    def _downsample_for_plot(self, data, max_points=4000):
        array = np.asarray(data, dtype=float)
        if array.size <= max_points:
            return np.arange(array.size), array

        indices = np.linspace(0, array.size - 1, max_points, dtype=int)
        return indices, array[indices]

    def _start_wavelet_task(self, action):
        if not self._require_ready_signal():
            return

        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(self, "提示", "当前已有小波任务正在执行，请稍候。")
            return

        self.level = self._current_level()
        threshold_ratio = self._safe_float(self.ui.LE_value, 0.08)
        substitute = self._safe_float(self.ui.LE_substitute, 0.0)
        self._set_busy(True, "小波分解" if action == "analyze" else "小波去噪")

        self.worker = WaveletThread(
            action=action,
            signal_data=self.y,
            wavelet_name=self.wavelet.name,
            mode=self.mode,
            level=self.level,
            lamda_mode=self.lamda_mode,
            option=self.option,
            threshold_ratio=threshold_ratio,
            substitute=substitute,
        )
        self.worker.finished_ok.connect(self._on_wavelet_finished)
        self.worker.failed.connect(self._on_wavelet_failed)
        self.worker.start()

    def my_wt(self):
        self._start_wavelet_task("analyze")

    def wt_denoiser(self):
        self._start_wavelet_task("denoise")

    def _on_wavelet_finished(self, result):
        self.coeffs = result["coeffs"]
        self.level = result["level"]

        if result["action"] == "analyze":
            self._plot_decomposition()
            self._set_busy(False)
            QMessageBox.information(self, "成功", "小波分解完成！")
            return

        self.newdata = result["newdata"]
        self.df_result = self.df.copy()
        self.df_result[self.selected_column] = self.newdata
        self._plot_denoise_result()
        self._set_busy(False)
        QMessageBox.information(self, "成功", "小波去噪完成，可传递到下游节点。")

    def _on_wavelet_failed(self, error_message):
        self.df_result = pd.DataFrame()
        self.newdata = np.array([], dtype=float)
        self._set_busy(False)
        QMessageBox.critical(self, "错误", f"小波处理失败：{error_message}")

    def on_overlap(self):
        if self.newdata.size == 0:
            QMessageBox.warning(self, "警告", "请先执行小波去噪，再进行叠加显示。")
            return
        self._plot_denoise_result()

    def on_Transfer(self):
        if self.df_result.empty or self.newdata.size == 0:
            QMessageBox.warning(self, "警告", "请先执行小波去噪，再传递结果。")
            return

        try:
            if self.node.LoadData(self.df_result):
                self.node.eval()
                self.node.evalChildren()
                QMessageBox.information(self, "成功", "小波去噪结果已传递给下游节点。")
            else:
                QMessageBox.critical(self, "错误", "结果传递失败！")
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"结果传递失败：{exc}")
