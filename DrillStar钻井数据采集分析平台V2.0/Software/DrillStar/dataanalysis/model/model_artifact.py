from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, Optional

import numpy as np
import pandas as pd


ARTIFACT_TYPE = "drillstar_model_artifact"
ARTIFACT_VERSION = 1


def is_model_artifact(value: Any) -> bool:
    return isinstance(value, dict) and value.get("artifact_type") == ARTIFACT_TYPE


def build_model_artifact(
    *,
    model_name: str,
    model: Any,
    task_type: str,
    feature_columns: Iterable[str],
    target_column: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
    metrics: Optional[Dict[str, Any]] = None,
    label_encoder: Any = None,
    preprocessor: Any = None,
    output_prefix: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "model_name": model_name,
        "task_type": task_type,
        "model": model,
        "feature_columns": [str(col) for col in feature_columns],
        "target_column": None if target_column is None else str(target_column),
        "params": params or {},
        "metrics": metrics or {},
        "label_encoder": label_encoder,
        "preprocessor": preprocessor,
        "output_prefix": output_prefix or _default_output_prefix(model_name),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "extra": extra or {},
    }


def artifact_summary(artifact: Dict[str, Any]) -> str:
    feature_columns = artifact.get("feature_columns") or []
    metrics = artifact.get("metrics") or {}
    lines = [
        f"模型：{artifact.get('model_name', 'Unknown')}",
        f"任务：{artifact.get('task_type', 'unknown')}",
        f"特征列数：{len(feature_columns)}",
    ]
    target_column = artifact.get("target_column")
    if target_column:
        lines.append(f"目标列：{target_column}")
    if metrics:
        metric_text = ", ".join(f"{key}={value}" for key, value in metrics.items())
        lines.append(f"指标：{metric_text}")
    created_at = artifact.get("created_at")
    if created_at:
        lines.append(f"创建时间：{created_at}")
    return "\n".join(lines)


def resolve_model_artifact(node: Any) -> Optional[Dict[str, Any]]:
    if node is None:
        return None

    value = getattr(node, "data", None)
    if is_model_artifact(value):
        return value

    try:
        serialized = node.serialize()
        value = serialized.get("value")
        if is_model_artifact(value):
            return value
    except Exception:
        pass

    window = getattr(node, "window", None)
    if window is None and hasattr(node, "_ensure_window"):
        try:
            window = node._ensure_window()
        except Exception:
            window = None

    if window is not None:
        artifact = getattr(window, "model_artifact", None)
        if is_model_artifact(artifact):
            return artifact
        model = getattr(window, "model", None)
        if model is not None:
            return build_artifact_from_window(window)

    return None


def build_artifact_from_window(window: Any) -> Optional[Dict[str, Any]]:
    model = getattr(window, "model", None)
    if model is None:
        return None

    model_name = _guess_model_name(window)
    task_type = _guess_task_type(model_name, model)
    feature_columns = _window_feature_columns(window)
    target_column = _window_target_column(window)
    params = getattr(window, "params", None) or {}
    label_encoder = getattr(window, "label_encoder", None)
    preprocessor = getattr(window, "preprocessor", None)
    return build_model_artifact(
        model_name=model_name,
        model=model,
        task_type=task_type,
        feature_columns=feature_columns,
        target_column=target_column,
        params=params,
        label_encoder=label_encoder,
        preprocessor=preprocessor,
    )


def run_artifact_prediction(artifact: Dict[str, Any], df: pd.DataFrame) -> pd.DataFrame:
    if not is_model_artifact(artifact):
        raise ValueError("输入不是有效的 DrillStar 模型包。")
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise ValueError("预测输入数据为空。")

    feature_columns = artifact.get("feature_columns") or []
    if not feature_columns:
        raise ValueError("模型包缺少特征列信息，无法对齐新数据。")

    missing = [col for col in feature_columns if col not in df.columns]
    if missing:
        raise ValueError("预测数据缺少特征列：" + ", ".join(map(str, missing)))

    x_df = df[feature_columns].apply(pd.to_numeric, errors="coerce")
    x_df = x_df.fillna(x_df.median(numeric_only=True)).fillna(0.0)
    model = artifact.get("model")
    preprocessor = artifact.get("preprocessor")
    task_type = artifact.get("task_type", "prediction")
    prefix = artifact.get("output_prefix") or _default_output_prefix(artifact.get("model_name", "Model"))

    x_input = preprocessor.transform(x_df) if preprocessor is not None else x_df
    if artifact.get("extra", {}).get("binarize_threshold") is not None:
        threshold = artifact["extra"]["binarize_threshold"]
        x_input = (x_input > threshold).astype(float)
    result_df = df.copy()

    if task_type in {"pca", "transform"}:
        transformed = model.transform(x_input)
        for index in range(transformed.shape[1]):
            result_df[f"{prefix}_PC{index + 1}"] = transformed[:, index]
        return result_df

    if task_type in {"cluster", "clustering"}:
        labels = model.predict(x_input)
        result_df[f"{prefix}_Cluster"] = labels
        if hasattr(model, "transform"):
            result_df[f"{prefix}_Distance"] = model.transform(x_input).min(axis=1)
        return result_df

    if not hasattr(model, "predict"):
        raise ValueError(f"{artifact.get('model_name', '当前模型')} 不支持通用 predict 接口。")

    predictions = model.predict(x_input)
    label_encoder = artifact.get("label_encoder")
    if label_encoder is not None:
        predictions = label_encoder.inverse_transform(np.asarray(predictions).astype(int))
    result_df[f"{prefix}_Prediction"] = predictions

    if hasattr(model, "predict_proba"):
        try:
            result_df[f"{prefix}_Confidence"] = model.predict_proba(x_input).max(axis=1)
        except Exception:
            pass

    return result_df


def _window_feature_columns(window: Any) -> Iterable[str]:
    if hasattr(window, "feature_columns"):
        value = getattr(window, "feature_columns")
        if value:
            return value
    if hasattr(window, "_selected_feature_columns"):
        try:
            value = window._selected_feature_columns()
            if value:
                return value
        except Exception:
            pass
    if hasattr(window, "selected_columns"):
        value = getattr(window, "selected_columns")
        if value:
            return value
    return []


def _window_target_column(window: Any) -> Optional[str]:
    if hasattr(window, "target_column"):
        value = getattr(window, "target_column")
        if value:
            return value
    combo = getattr(window, "combo_target", None)
    if combo is not None:
        try:
            return combo.currentText()
        except Exception:
            return None
    return None


def _guess_model_name(window: Any) -> str:
    title = ""
    try:
        title = window.windowTitle()
    except Exception:
        pass
    if "[" in title and "]" in title:
        return title.split("[", 1)[1].split("]", 1)[0].strip()
    return window.__class__.__name__.replace("Win_Model", "")


def _guess_task_type(model_name: str, model: Any) -> str:
    name = model_name.lower()
    if "pca" in name:
        return "pca"
    if "kmeans" in name or "k-means" in name:
        return "cluster"
    if "linear" in name or "lstm" in name or "informer" in name:
        return "regression"
    if hasattr(model, "predict_proba"):
        return "classification"
    return "prediction"


def _default_output_prefix(model_name: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(model_name)).strip("_") or "Model"
