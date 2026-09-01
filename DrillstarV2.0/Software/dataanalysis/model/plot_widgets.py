import numpy as np
import pandas as pd
from PyQt5.QtWidgets import QSizePolicy, QWidget, QVBoxLayout

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from sklearn.decomposition import PCA


class ModelPlotWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.figure = Figure(figsize=(6, 4), tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

        self.setMinimumHeight(280)
        self.clear("Run the model to show the chart.")

    def clear(self, message="No chart available."):
        self.figure.clear()
        axis = self.figure.add_subplot(111)
        axis.text(0.5, 0.5, message, ha="center", va="center", color="#6b7280")
        axis.set_axis_off()
        self.canvas.draw_idle()

    def plot_kmeans(self, df, feature_columns, label_column="KMeans_Cluster", model=None, preprocessor=None):
        if df is None or df.empty or not feature_columns or label_column not in df.columns:
            self.clear("No clustering result to plot.")
            return

        feature_df = df[feature_columns].apply(pd.to_numeric, errors="coerce")
        feature_df = feature_df.fillna(feature_df.median(numeric_only=True)).fillna(0.0)
        x_values = feature_df.to_numpy()
        if preprocessor is not None:
            x_values = preprocessor.transform(x_values)

        labels = pd.to_numeric(df[label_column], errors="coerce")
        valid_mask = labels.notna()
        x_values = x_values[valid_mask.to_numpy()]
        labels = labels[valid_mask].astype(int).to_numpy()
        if len(labels) == 0:
            self.clear("No valid cluster labels.")
            return

        self.figure.clear()
        axis = self.figure.add_subplot(111)

        centers_2d = None
        if x_values.shape[1] == 1:
            plot_x = np.arange(len(x_values))
            plot_y = x_values[:, 0]
            x_label = "Sample"
            y_label = str(feature_columns[0])
        elif x_values.shape[1] == 2:
            plot_x = x_values[:, 0]
            plot_y = x_values[:, 1]
            x_label = str(feature_columns[0])
            y_label = str(feature_columns[1])
            if model is not None and hasattr(model, "cluster_centers_"):
                centers_2d = model.cluster_centers_
        else:
            reducer = PCA(n_components=2)
            points_2d = reducer.fit_transform(x_values)
            plot_x = points_2d[:, 0]
            plot_y = points_2d[:, 1]
            x_label = "PCA 1"
            y_label = "PCA 2"
            if model is not None and hasattr(model, "cluster_centers_"):
                centers_2d = reducer.transform(model.cluster_centers_)

        scatter = axis.scatter(plot_x, plot_y, c=labels, cmap="tab10", s=28, alpha=0.82, edgecolors="none")
        if centers_2d is not None:
            axis.scatter(
                centers_2d[:, 0],
                centers_2d[:, 1],
                c="black",
                marker="x",
                s=90,
                linewidths=2,
                label="Centers",
            )
            axis.legend(loc="best")

        axis.set_title("K-Means Clusters")
        axis.set_xlabel(x_label)
        axis.set_ylabel(y_label)
        axis.grid(True, alpha=0.25)
        self.figure.colorbar(scatter, ax=axis, label="Cluster")
        self.canvas.draw_idle()

    def plot_regression(self, df, target_column, prediction_column, residual_column=None):
        actual, predicted, valid_frame = self._regression_series(df, target_column, prediction_column)
        if len(actual) == 0:
            self.clear("No valid regression result to plot.")
            return

        residuals = actual - predicted
        self.figure.clear()
        ax_fit = self.figure.add_subplot(211)
        ax_res = self.figure.add_subplot(212)

        ax_fit.scatter(actual, predicted, s=24, alpha=0.75, color="#2563eb", edgecolors="none")
        min_value = float(np.nanmin([actual.min(), predicted.min()]))
        max_value = float(np.nanmax([actual.max(), predicted.max()]))
        ax_fit.plot([min_value, max_value], [min_value, max_value], color="#dc2626", linewidth=1.5)
        ax_fit.set_title("Actual vs Predicted")
        ax_fit.set_xlabel("Actual")
        ax_fit.set_ylabel("Predicted")
        ax_fit.grid(True, alpha=0.25)

        if residual_column and residual_column in df.columns:
            residual_series = pd.to_numeric(df.loc[valid_frame.index, residual_column], errors="coerce")
            residuals = residual_series.where(residual_series.notna(), residuals).to_numpy()
        ax_res.axhline(0, color="#111827", linewidth=1)
        ax_res.scatter(np.arange(len(residuals)), residuals, s=20, alpha=0.75, color="#059669", edgecolors="none")
        ax_res.set_title("Residuals")
        ax_res.set_xlabel("Sample")
        ax_res.set_ylabel("Actual - Predicted")
        ax_res.grid(True, alpha=0.25)

        self.canvas.draw_idle()

    def plot_timeseries_prediction(self, df, target_column, prediction_column):
        actual, predicted, valid_frame = self._regression_series(df, target_column, prediction_column)
        if len(actual) == 0:
            self.clear("No valid time-series result to plot.")
            return

        x_axis = np.arange(len(valid_frame))
        self.figure.clear()
        axis = self.figure.add_subplot(111)
        axis.plot(x_axis, actual, color="#111827", linewidth=1.6, label="Actual")
        axis.plot(x_axis, predicted, color="#dc2626", linewidth=1.4, label="Predicted")
        axis.set_title("Actual vs Predicted")
        axis.set_xlabel("Sample")
        axis.set_ylabel(str(target_column))
        axis.grid(True, alpha=0.25)
        axis.legend(loc="best")
        self.canvas.draw_idle()

    def _regression_series(self, df, target_column, prediction_column):
        if df is None or df.empty or target_column not in df.columns or prediction_column not in df.columns:
            return np.array([]), np.array([]), pd.DataFrame()

        frame = df[[target_column, prediction_column]].copy()
        frame[target_column] = pd.to_numeric(frame[target_column], errors="coerce")
        frame[prediction_column] = pd.to_numeric(frame[prediction_column], errors="coerce")
        frame = frame.dropna()
        return frame[target_column].to_numpy(), frame[prediction_column].to_numpy(), frame
