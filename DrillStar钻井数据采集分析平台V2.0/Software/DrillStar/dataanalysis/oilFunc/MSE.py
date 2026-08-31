import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QLabel, QMessageBox, QSizePolicy, QWidget

from dataanalysis.async_task import BusyTaskMixin
from dataanalysis.ui.oilFuncMSE_ui import Ui_OilFuncMSE


pg.setConfigOptions(antialias=True, useOpenGL=False, enableExperimental=False)


class DateTimeAxisItem(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        labels = []
        for value in values:
            ts = pd.to_datetime(value, unit="s", errors="coerce")
            labels.append("" if pd.isna(ts) else ts.strftime("%m-%d\n%H:%M:%S"))
        return labels


@dataclass
class MSEFieldSelection:
    wob: object
    toq: object
    rpm: object
    rate_col: object
    time_col: object
    depth_col: object
    rate_mode: str


class Win_OilFuncMSE(QWidget, Ui_OilFuncMSE, BusyTaskMixin):
    RATE_MODE_DIRECT = "direct_rop"
    RATE_MODE_DRILL_TIME_MIN = "drill_time_min_per_m"
    RATE_MODE_DRILL_TIME_SEC = "drill_time_sec_per_m"
    RATE_MODE_DRILL_TIME_HOUR = "drill_time_hour_per_m"
    RATE_MODE_TIME_DEPTH = "time_depth"

    def __init__(self, node: object):
        super().__init__()
        self.setupUi(self)
        self.btn_Load.setText("Load")
        self.btn_Calculate.setText("Calculate")
        self.btn_Transfer.setText("Transfer")
        self.setWindowTitle("OilFunc [MSE计算]")

        setattr(node, "window", self)
        self.node = node

        self.df_source = pd.DataFrame()
        self.df_output = pd.DataFrame()
        self.column_lookup = {}
        self.plot_widget = None
        self.max_points = 12000
        self.raw_color = QColor(0, 114, 189)
        self.smooth_color = QColor(217, 83, 25)

        self._init_rate_modes()
        self._bind_signals()
        self._load_formula_text()
        self.le_BitDiameter.setText("215.9")

    def _bind_signals(self):
        self.btn_Load.clicked.connect(self.on_load)
        self.btn_Calculate.clicked.connect(self.on_calculate)
        self.btn_Transfer.clicked.connect(self.on_transfer)
        self.btn_Clear.clicked.connect(self.clear_plots)
        self.cB_RateMode.currentIndexChanged.connect(self._update_rate_mode_hint)

    def _init_rate_modes(self):
        self.cB_RateMode.clear()
        self.cB_RateMode.addItem("直接使用ROP", self.RATE_MODE_DIRECT)
        self.cB_RateMode.addItem("钻时换算ROP(min/m)", self.RATE_MODE_DRILL_TIME_MIN)
        self.cB_RateMode.addItem("钻时换算ROP(s/m)", self.RATE_MODE_DRILL_TIME_SEC)
        self.cB_RateMode.addItem("钻时换算ROP(h/m)", self.RATE_MODE_DRILL_TIME_HOUR)
        self.cB_RateMode.addItem("时间深度反算ROP", self.RATE_MODE_TIME_DEPTH)
        self._update_rate_mode_hint()

    def _load_formula_text(self):
        self.label_Math.setText(
            "MSE = WOB / A + 2π × RPM × T / (A × ROP)\n"
            "其中 A = πD² / 4，D 为钻头直径。\n"
            "支持直接使用 ROP、由钻时换算 ROP，以及由时间列和深度列反算 ROP。"
        )

    def _update_rate_mode_hint(self):
        mode = self.cB_RateMode.currentData()
        if mode == self.RATE_MODE_DIRECT:
            hint = "当前模式：直接使用已有 ROP 列。"
            self.cB_RateColumn.setEnabled(True)
        elif mode == self.RATE_MODE_DRILL_TIME_MIN:
            hint = "当前模式：将钻时按 min/m 换算为 ROP，公式为 ROP = 60 / 钻时。"
            self.cB_RateColumn.setEnabled(True)
        elif mode == self.RATE_MODE_DRILL_TIME_SEC:
            hint = "当前模式：将钻时按 s/m 换算为 ROP，公式为 ROP = 3600 / 钻时。"
            self.cB_RateColumn.setEnabled(True)
        elif mode == self.RATE_MODE_DRILL_TIME_HOUR:
            hint = "当前模式：将钻时按 h/m 换算为 ROP，公式为 ROP = 1 / 钻时。"
            self.cB_RateColumn.setEnabled(True)
        else:
            hint = "当前模式：根据时间列和深度列反算 ROP，适合时序数据。"
            self.cB_RateColumn.setEnabled(False)
        self.label_RateHint.setText(hint)

    def _normalize_text(self, value):
        return str(value).strip().lower().replace(" ", "")

    def _normalize_datetime_columns(self, df):
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                continue
            col_text = str(col).lower()
            if any(key in col_text for key in ["time", "date", "timestamp", "日期", "时间"]):
                try:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
                except Exception:
                    pass
        return df

    def _get_input_df(self):
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

    def _build_column_lookup(self):
        self.column_lookup = {str(col): col for col in self.df_source.columns}

    def _set_combobox_items(self, combo, items, allow_empty=False):
        current_text = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        if allow_empty:
            combo.addItem("")
        combo.addItems(items)
        if current_text and combo.findText(current_text) >= 0:
            combo.setCurrentText(current_text)
        combo.blockSignals(False)

    def _get_actual_column(self, combo):
        text = combo.currentText().strip()
        if not text:
            return None
        return self.column_lookup.get(text)

    def _find_best_column(self, candidates, keywords):
        best_col = None
        best_score = -1
        for col in candidates:
            col_text = self._normalize_text(col)
            raw_text = str(col)
            score = 0
            for keyword in keywords:
                kw_text = self._normalize_text(keyword)
                if col_text == kw_text:
                    score += 10
                elif kw_text and kw_text in col_text:
                    score += 5
                if keyword in raw_text:
                    score += 2
            if score > best_score:
                best_score = score
                best_col = col
        return best_col if best_score > 0 else None

    def on_load(self):
        try:
            df = self._get_input_df()
            if df.empty:
                QMessageBox.warning(self, "提示", "上游节点没有有效数据。")
                return

            self.df_source = self._normalize_datetime_columns(df)
            self.df_output = pd.DataFrame()
            self.clear_plots()
            self._build_column_lookup()
            self._fill_comboboxes()

            time_col = self._find_best_column(self.df_source.columns.tolist(), ["time", "date", "timestamp", "日期", "时间"])
            depth_col = self._find_best_column(
                self.df_source.select_dtypes(include=[np.number]).columns.tolist(),
                ["depth", "md", "井深", "测深", "深度"],
            )
            self.label_Summary.setText(
                f"当前状态：已加载 {self.df_source.shape[0]} 行 × {self.df_source.shape[1]} 列，"
                f"建议时间列为 {time_col or '未识别'}，建议深度列为 {depth_col or '未识别'}。"
            )
            QMessageBox.information(self, "成功", "MSE 数据已加载。")
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"加载失败：{exc}")

    def _fill_comboboxes(self):
        all_cols = [str(col) for col in self.df_source.columns.tolist()]
        numeric_cols = [str(col) for col in self.df_source.select_dtypes(include=[np.number]).columns.tolist()]

        self._set_combobox_items(self.cB_WOB, numeric_cols)
        self._set_combobox_items(self.cB_TOQ, numeric_cols)
        self._set_combobox_items(self.cB_RPM, numeric_cols)
        self._set_combobox_items(self.cB_RateColumn, numeric_cols, allow_empty=True)
        self._set_combobox_items(self.cB_TimeColumn, all_cols, allow_empty=True)
        self._set_combobox_items(self.cB_DepthColumn, numeric_cols, allow_empty=True)

        wob_col = self._find_best_column(numeric_cols, ["wob", "钻压", "weight"])
        toq_col = self._find_best_column(numeric_cols, ["toq", "torque", "扭矩"])
        rpm_col = self._find_best_column(numeric_cols, ["rpm", "转速", "rotary"])
        rop_col = self._find_best_column(numeric_cols, ["rop", "钻速", "机械钻速", "rate"])
        drill_time_col = self._find_best_column(numeric_cols, ["钻时", "单米钻时", "min/m", "s/m", "sec/m", "小时/米"])
        time_col = self._find_best_column(all_cols, ["time", "date", "timestamp", "日期", "时间"])
        depth_col = self._find_best_column(numeric_cols, ["depth", "md", "井深", "测深", "深度"])

        if wob_col:
            self.cB_WOB.setCurrentText(str(wob_col))
        if toq_col:
            self.cB_TOQ.setCurrentText(str(toq_col))
        if rpm_col:
            self.cB_RPM.setCurrentText(str(rpm_col))
        if time_col:
            self.cB_TimeColumn.setCurrentText(str(time_col))
        if depth_col:
            self.cB_DepthColumn.setCurrentText(str(depth_col))

        if rop_col:
            self.cB_RateMode.setCurrentIndex(self.cB_RateMode.findData(self.RATE_MODE_DIRECT))
            self.cB_RateColumn.setCurrentText(str(rop_col))
        elif drill_time_col:
            self.cB_RateMode.setCurrentIndex(self.cB_RateMode.findData(self.RATE_MODE_DRILL_TIME_MIN))
            self.cB_RateColumn.setCurrentText(str(drill_time_col))
        elif time_col and depth_col:
            self.cB_RateMode.setCurrentIndex(self.cB_RateMode.findData(self.RATE_MODE_TIME_DEPTH))

        if self.cB_RateColumn.count() > 1 and not self.cB_RateColumn.currentText():
            self.cB_RateColumn.setCurrentIndex(1)
        self._update_rate_mode_hint()

    def _get_selection(self):
        selection = MSEFieldSelection(
            wob=self._get_actual_column(self.cB_WOB),
            toq=self._get_actual_column(self.cB_TOQ),
            rpm=self._get_actual_column(self.cB_RPM),
            rate_col=self._get_actual_column(self.cB_RateColumn),
            time_col=self._get_actual_column(self.cB_TimeColumn),
            depth_col=self._get_actual_column(self.cB_DepthColumn),
            rate_mode=self.cB_RateMode.currentData(),
        )
        if not selection.wob or not selection.toq or not selection.rpm:
            raise ValueError("请完整选择 WOB、TOQ 和 RPM 列。")
        if selection.rate_mode != self.RATE_MODE_TIME_DEPTH and not selection.rate_col:
            raise ValueError("请先选择 ROP 列或钻时列。")
        if selection.rate_mode == self.RATE_MODE_TIME_DEPTH and (not selection.time_col or not selection.depth_col):
            raise ValueError("时间深度反算 ROP 时，必须选择时间列和深度列。")
        return selection

    def _get_bit_diameter_meter(self):
        text = self.le_BitDiameter.text().strip()
        if not text:
            raise ValueError("请输入钻头直径。")
        diameter_mm = float(text)
        if diameter_mm <= 0:
            raise ValueError("钻头直径必须大于 0。")
        return diameter_mm / 1000.0

    def _compute_rop_series(self, selection):
        if selection.rate_mode == self.RATE_MODE_DIRECT:
            return pd.to_numeric(self.df_source[selection.rate_col], errors="coerce"), f"直接使用列 {selection.rate_col}"

        if selection.rate_mode in (self.RATE_MODE_DRILL_TIME_MIN, self.RATE_MODE_DRILL_TIME_SEC, self.RATE_MODE_DRILL_TIME_HOUR):
            drill_time = pd.to_numeric(self.df_source[selection.rate_col], errors="coerce").where(lambda x: x > 0)
            if selection.rate_mode == self.RATE_MODE_DRILL_TIME_MIN:
                return 60.0 / drill_time, f"钻时(min/m)换算列 {selection.rate_col}"
            if selection.rate_mode == self.RATE_MODE_DRILL_TIME_SEC:
                return 3600.0 / drill_time, f"钻时(s/m)换算列 {selection.rate_col}"
            return 1.0 / drill_time, f"钻时(h/m)换算列 {selection.rate_col}"

        time_series = pd.to_datetime(self.df_source[selection.time_col], errors="coerce")
        depth_series = pd.to_numeric(self.df_source[selection.depth_col], errors="coerce")
        calc_df = pd.DataFrame({"time": time_series, "depth": depth_series}, index=self.df_source.index).dropna().sort_values("time")
        if calc_df.empty:
            return pd.Series(np.nan, index=self.df_source.index), "时间深度反算"
        time_diff = calc_df["time"].diff().dt.total_seconds()
        depth_diff = calc_df["depth"].diff()
        rop = (depth_diff / time_diff) * 3600.0
        rop = rop.where((time_diff > 0) & (depth_diff > 0))
        rop = rop.rolling(7, min_periods=1, center=True).median()
        return rop.reindex(self.df_source.index), f"由时间列 {selection.time_col} 和深度列 {selection.depth_col} 反算"

    def _prepare_output_dataframe(self, selection, bit_diameter_m):
        rop_series, rate_source = self._compute_rop_series(selection)
        calc_df = pd.DataFrame(index=self.df_source.index)
        calc_df["WOB"] = pd.to_numeric(self.df_source[selection.wob], errors="coerce")
        calc_df["TOQ"] = pd.to_numeric(self.df_source[selection.toq], errors="coerce")
        calc_df["RPM"] = pd.to_numeric(self.df_source[selection.rpm], errors="coerce")
        calc_df["ROP"] = pd.to_numeric(rop_series, errors="coerce")

        valid_df = calc_df.replace([np.inf, -np.inf], np.nan).dropna()
        valid_df = valid_df[(valid_df["ROP"] > 0) & (valid_df["WOB"] >= 0) & (valid_df["TOQ"] >= 0) & (valid_df["RPM"] >= 0)]
        if valid_df.empty:
            raise ValueError("清洗后无有效数据，无法完成 MSE 计算。")

        area = math.pi * bit_diameter_m**2 / 4.0
        wob_n = valid_df["WOB"].to_numpy() * 1000.0
        torque_nm = valid_df["TOQ"].to_numpy() * 1000.0
        rpm = valid_df["RPM"].to_numpy()
        rop_mps = valid_df["ROP"].to_numpy() / 3600.0
        mse_value = ((wob_n / area) + (2.0 * math.pi * rpm * torque_nm) / (area * rop_mps * 60.0)) / 1e6
        mse_series = pd.Series(mse_value, index=valid_df.index, dtype=float)
        mse_smooth = mse_series.rolling(15, min_periods=1, center=True).median()

        output_df = self.df_source.copy()
        output_df["ROP_计算值"] = rop_series
        output_df["MSE"] = np.nan
        output_df["MSE_平滑"] = np.nan
        output_df.loc[mse_series.index, "MSE"] = mse_series
        output_df.loc[mse_smooth.index, "MSE_平滑"] = mse_smooth
        return output_df, rate_source, len(mse_series)

    def on_calculate(self):
        try:
            if self.df_source.empty:
                QMessageBox.warning(self, "提示", "请先加载数据。")
                return
            selection = self._get_selection()
            bit_diameter_m = self._get_bit_diameter_meter()
            self._start_background_task(
                "MSE分析",
                "正在计算机械比能，请稍候...",
                self._prepare_output_dataframe,
                lambda result: self._on_calculate_finished(selection, result),
                self._on_calculate_failed,
                selection,
                bit_diameter_m,
            )
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"MSE 计算失败：{exc}")

    def _on_calculate_finished(self, selection, result):
        self.df_output, rate_source, valid_count = result
        self.draw_mse_plot(selection)
        valid_mse = self.df_output["MSE"].dropna()
        self.label_Summary.setText(
            f"当前状态：MSE 计算完成，有效样本 {valid_count}/{len(self.df_output)}，ROP 来源为 {rate_source}。"
        )
        QMessageBox.information(
            self,
            "成功",
            f"MSE 计算完成。\nP50={valid_mse.median():.2f}，P90={valid_mse.quantile(0.9):.2f}",
        )

    def _on_calculate_failed(self, message):
        QMessageBox.critical(self, "错误", f"MSE 计算失败：{message}")

    def _get_plot_data(self, selection):
        plot_df = self.df_output.loc[self.df_output["MSE"].notna()].copy()
        if plot_df.empty:
            return np.array([]), np.array([]), np.array([]), "样本点", False
        if selection.time_col and selection.time_col in plot_df.columns:
            time_series = pd.to_datetime(plot_df[selection.time_col], errors="coerce").dropna()
            if len(time_series) > 1:
                plot_df = plot_df.loc[time_series.index]
                return (
                    (time_series.astype("int64") // 10**9).to_numpy(dtype=float),
                    plot_df["MSE"].to_numpy(dtype=float),
                    plot_df["MSE_平滑"].to_numpy(dtype=float),
                    "时间",
                    True,
                )
        return (
            plot_df.index.to_numpy(dtype=float),
            plot_df["MSE"].to_numpy(dtype=float),
            plot_df["MSE_平滑"].to_numpy(dtype=float),
            "样本点",
            False,
        )

    def _sample_plot_data(self, x_data, y_raw, y_smooth):
        if len(x_data) <= self.max_points:
            return x_data, y_raw, y_smooth
        step = max(1, len(x_data) // self.max_points)
        return x_data[::step], y_raw[::step], y_smooth[::step]

    def draw_mse_plot(self, selection):
        self.clear_plots()
        x_data, y_raw, y_smooth, x_label, use_time_axis = self._get_plot_data(selection)
        if len(x_data) == 0:
            return
        x_data, y_raw, y_smooth = self._sample_plot_data(x_data, y_raw, y_smooth)
        axis_items = {"bottom": DateTimeAxisItem(orientation="bottom")} if use_time_axis else None
        self.plot_widget = pg.PlotWidget(axisItems=axis_items)
        self.plot_widget.setBackground("w")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.35)
        self.plot_widget.setClipToView(True)
        self.plot_widget.setDownsampling(mode="peak")
        self.plot_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.plot_widget.setLabel("left", "MSE")
        self.plot_widget.setLabel("bottom", x_label)
        self.plot_widget.plot(x_data, y_raw, pen=pg.mkPen(color=self.raw_color, width=1.0, cosmetic=True), name="MSE")
        self.plot_widget.plot(x_data, y_smooth, pen=pg.mkPen(color=self.smooth_color, width=2.0, cosmetic=True), name="MSE平滑")
        self.verticalLayout_plot.addWidget(self.plot_widget)

    def on_transfer(self):
        try:
            if self.df_output.empty:
                QMessageBox.warning(self, "提示", "请先完成 MSE 计算。")
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
            QMessageBox.information(self, "成功", "包含 MSE 结果的新数据已传递到下游节点。")
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"结果传递失败：{exc}")

    def clear_plots(self):
        while self.verticalLayout_plot.count():
            item = self.verticalLayout_plot.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.plot_widget = None

    def closeEvent(self, event):
        self.hide()
        event.ignore()


def _mse_draw_plot_with_legend(self, selection):
    self.clear_plots()
    x_data, y_raw, y_smooth, x_label, use_time_axis = self._get_plot_data(selection)
    if len(x_data) == 0:
        return

    x_data, y_raw, y_smooth = self._sample_plot_data(x_data, y_raw, y_smooth)
    axis_items = {"bottom": DateTimeAxisItem(orientation="bottom")} if use_time_axis else None
    self.plot_widget = pg.PlotWidget(axisItems=axis_items)
    self.plot_widget.setBackground("w")
    self.plot_widget.showGrid(x=True, y=True, alpha=0.35)
    self.plot_widget.setClipToView(True)
    self.plot_widget.setDownsampling(mode="peak")
    self.plot_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    self.plot_widget.setLabel("left", "MSE")
    self.plot_widget.setLabel("bottom", x_label)
    self.plot_widget.addLegend(offset=(10, 10))
    self.plot_widget.plot(
        x_data,
        y_raw,
        pen=pg.mkPen(color=self.raw_color, width=1.0, cosmetic=True),
        name="原始 MSE",
    )
    self.plot_widget.plot(
        x_data,
        y_smooth,
        pen=pg.mkPen(color=self.smooth_color, width=2.0, cosmetic=True),
        name="平滑 MSE",
    )
    self.verticalLayout_plot.addWidget(self.plot_widget)


Win_OilFuncMSE.draw_mse_plot = _mse_draw_plot_with_legend


def _mse_ensure_time_label(self):
    if getattr(self, "label_time_range", None) is None:
        self.label_time_range = QLabel("当前选中时间：无", self)
        self.label_time_range.setAlignment(Qt.AlignCenter)
        self.label_time_range.setMinimumHeight(40)
        self.label_time_range.setStyleSheet("border: 1px solid #cccccc; border-radius: 4px; padding: 5px;")
        insert_index = self.verticalLayout_2.indexOf(self.scrollArea)
        if insert_index < 0:
            self.verticalLayout_2.addWidget(self.label_time_range)
        else:
            self.verticalLayout_2.insertWidget(insert_index, self.label_time_range)


def _mse_prepare_output_dataframe_no_smooth(self, selection, bit_diameter_m):
    rop_series, rate_source = self._compute_rop_series(selection)
    calc_df = pd.DataFrame(index=self.df_source.index)
    calc_df["WOB"] = pd.to_numeric(self.df_source[selection.wob], errors="coerce")
    calc_df["TOQ"] = pd.to_numeric(self.df_source[selection.toq], errors="coerce")
    calc_df["RPM"] = pd.to_numeric(self.df_source[selection.rpm], errors="coerce")
    calc_df["ROP"] = pd.to_numeric(rop_series, errors="coerce")

    valid_df = calc_df.replace([np.inf, -np.inf], np.nan).dropna()
    valid_df = valid_df[(valid_df["ROP"] > 0) & (valid_df["WOB"] >= 0) & (valid_df["TOQ"] >= 0) & (valid_df["RPM"] >= 0)]
    if valid_df.empty:
        raise ValueError("清洗后无有效数据，无法完成 MSE 计算。")

    area = math.pi * bit_diameter_m**2 / 4.0
    wob_n = valid_df["WOB"].to_numpy() * 1000.0
    torque_nm = valid_df["TOQ"].to_numpy() * 1000.0
    rpm = valid_df["RPM"].to_numpy()
    rop_mps = valid_df["ROP"].to_numpy() / 3600.0
    mse_value = ((wob_n / area) + (2.0 * math.pi * rpm * torque_nm) / (area * rop_mps * 60.0)) / 1e6
    mse_series = pd.Series(mse_value, index=valid_df.index, dtype=float)

    output_df = self.df_source.copy()
    output_df["ROP_计算值"] = rop_series
    output_df["MSE"] = np.nan
    output_df.loc[mse_series.index, "MSE"] = mse_series
    return output_df, rate_source, len(mse_series)


def _mse_get_plot_data_single(self, selection):
    plot_df = self.df_output.loc[self.df_output["MSE"].notna()].copy()
    if plot_df.empty:
        return np.array([]), np.array([]), "样本点", False
    if selection.time_col and selection.time_col in plot_df.columns:
        time_series = pd.to_datetime(plot_df[selection.time_col], errors="coerce").dropna()
        if len(time_series) > 1:
            plot_df = plot_df.loc[time_series.index]
            return (
                (time_series.astype("int64") // 10**9).to_numpy(dtype=float),
                plot_df["MSE"].to_numpy(dtype=float),
                "时间",
                True,
            )
    return (
        plot_df.index.to_numpy(dtype=float),
        plot_df["MSE"].to_numpy(dtype=float),
        "样本点",
        False,
    )


def _mse_update_time_range_label(self, x_data):
    if not getattr(self, "linear_region", None) or len(x_data) == 0 or not getattr(self, "_use_time_axis", False):
        self.label_time_range.setText("当前选中时间：无")
        return
    min_time_num, max_time_num = self.linear_region.getRegion()
    start_time = pd.to_datetime(min_time_num, unit="s", errors="coerce")
    end_time = pd.to_datetime(max_time_num, unit="s", errors="coerce")
    if pd.isna(start_time) or pd.isna(end_time):
        self.label_time_range.setText("当前选中时间：无")
        return
    self.label_time_range.setText(
        f"当前选中时间：\n{start_time.strftime('%Y-%m-%d %H:%M:%S')}\n至\n{end_time.strftime('%Y-%m-%d %H:%M:%S')}"
    )


def _mse_draw_plot_single(self, selection):
    self.clear_plots()
    self._mse_ensure_time_label()
    x_data, y_raw, x_label, use_time_axis = self._get_plot_data(selection)
    self._use_time_axis = use_time_axis
    if len(x_data) == 0:
        self.label_time_range.setText("当前选中时间：无")
        return

    if len(x_data) > self.max_points:
        step = max(1, len(x_data) // self.max_points)
        x_data = x_data[::step]
        y_raw = y_raw[::step]

    axis_items = {"bottom": DateTimeAxisItem(orientation="bottom")} if use_time_axis else None
    self.plot_widget = pg.PlotWidget(axisItems=axis_items)
    self.plot_widget.setBackground("w")
    self.plot_widget.showGrid(x=True, y=True, alpha=0.35)
    self.plot_widget.setClipToView(True)
    self.plot_widget.setDownsampling(mode="peak")
    self.plot_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    self.plot_widget.setLabel("left", "MSE")
    self.plot_widget.setLabel("bottom", x_label)
    self.plot_widget.plot(x_data, y_raw, pen=pg.mkPen(color=self.raw_color, width=1.5, cosmetic=True))

    self.linear_region = None
    if use_time_axis and len(x_data) > 1:
        min_time = float(x_data.min())
        max_time = float(x_data.max())
        default_right = min_time + max((max_time - min_time) * 0.1, 1.0)
        self.linear_region = pg.LinearRegionItem(
            [min_time, min(default_right, max_time)],
            pen=pg.mkPen(QColor(0, 0, 0), width=1.5),
            brush=pg.mkBrush(QColor(0, 0, 255, 30)),
            movable=True,
        )
        self.linear_region.sigRegionChanged.connect(lambda: self._update_time_range_label(x_data))
        self.plot_widget.addItem(self.linear_region)

    self.verticalLayout_plot.addWidget(self.plot_widget)
    self._update_time_range_label(x_data)


Win_OilFuncMSE._mse_ensure_time_label = _mse_ensure_time_label
Win_OilFuncMSE._prepare_output_dataframe = _mse_prepare_output_dataframe_no_smooth
Win_OilFuncMSE._get_plot_data = _mse_get_plot_data_single
Win_OilFuncMSE._update_time_range_label = _mse_update_time_range_label
Win_OilFuncMSE.draw_mse_plot = _mse_draw_plot_single
