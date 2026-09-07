"""Calibrated HGB twin heads: churn probability, 90d LTV, days-to-next-buy."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, roc_auc_score
from sklearn.model_selection import train_test_split

from src.features import FEATURE_COLUMNS, build_features, model_matrix


def _latent_labels(feat: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    z = (
        1.55 * feat["inactivity_pressure"]
        + 1.15 * feat["service_pressure"]
        + 0.95 * feat["price_pressure"]
        - 2.05 * feat["sales_strength"]
        - 1.10 * feat["email_open_rate"]
        + 0.07 * feat["support_tickets"]
        - 0.015 * np.log1p(feat["tenure_days"])
    )
    p = 1.0 / (1.0 + np.exp(-z))
    p = np.clip(p, 0.03, 0.94)
    churned = rng.binomial(1, p)
    # Guarantee both classes for calibration.
    if churned.sum() < 8:
        worst = np.argsort(p)[-12:]
        churned[worst] = 1
    if (1 - churned).sum() < 8:
        best = np.argsort(p)[:12]
        churned[best] = 0
    next_days = np.clip(feat["cycle_days"] * (0.7 + 0.85 * p) + rng.normal(0, 5, len(feat)), 4, 210)
    ltv90 = np.clip(feat["monetary_90_raw"] * (1 - 0.82 * p) * rng.uniform(0.88, 1.1, len(feat)), 0, None)
    out = feat.copy()
    out["y_churn"] = churned
    out["y_next_days"] = next_days
    out["y_ltv90"] = ltv90
    return out


@dataclass
class TwinModels:
    churn: CalibratedClassifierCV
    ltv: HistGradientBoostingRegressor
    next_purchase: HistGradientBoostingRegressor
    feature_names: list[str]
    metrics: dict[str, float] = field(default_factory=dict)
    importances: pd.DataFrame | None = None

    def predict_frame(self, feat: pd.DataFrame) -> pd.DataFrame:
        x = model_matrix(feat)
        p_churn = self.churn.predict_proba(x)[:, 1]
        ltv = np.clip(self.ltv.predict(x), 0, None)
        next_days = np.clip(self.next_purchase.predict(x), 1, 240)
        ltv_adj = ltv * (1.0 - 0.75 * p_churn)
        health = np.clip(feat["health_decay"] * (1.0 - 0.42 * p_churn) + 6.0, 1.0, 99.0)
        out = feat.copy()
        out["p_churn"] = p_churn
        out["ltv_90"] = ltv
        out["ltv_90_adj"] = ltv_adj
        out["next_days"] = next_days
        out["health"] = health
        out["at_risk"] = p_churn >= 0.45
        out["sales_high"] = out["sales_strength"] >= 0.62
        out["churn_high"] = p_churn >= 0.45
        return out


def train_twin_models(panel: pd.DataFrame, seed: int = 42) -> TwinModels:
    rng = np.random.default_rng(seed)
    feat = build_features(panel)
    labeled = _latent_labels(feat, rng)
    x = model_matrix(labeled)

    x_train, x_test, y_c_train, y_c_test = train_test_split(
        x,
        labeled["y_churn"],
        test_size=0.25,
        random_state=seed,
        stratify=labeled["y_churn"],
    )
    y_ltv_train = labeled.loc[x_train.index, "y_ltv90"]
    y_next_train = labeled.loc[x_train.index, "y_next_days"]

    clf_core = HistGradientBoostingClassifier(
        max_depth=5,
        learning_rate=0.07,
        max_iter=220,
        l2_regularization=0.12,
        min_samples_leaf=12,
        random_state=seed,
    )
    churn = CalibratedClassifierCV(clf_core, method="isotonic", cv=3)
    churn.fit(x_train, y_c_train)

    ltv = HistGradientBoostingRegressor(
        max_depth=5,
        learning_rate=0.07,
        max_iter=220,
        l2_regularization=0.12,
        min_samples_leaf=12,
        random_state=seed,
    )
    nxt = HistGradientBoostingRegressor(
        max_depth=5,
        learning_rate=0.07,
        max_iter=200,
        l2_regularization=0.12,
        min_samples_leaf=12,
        random_state=seed,
    )
    ltv.fit(x_train, y_ltv_train)
    nxt.fit(x_train, y_next_train)

    p_test = churn.predict_proba(x_test)[:, 1]
    auc = float(roc_auc_score(y_c_test, p_test))
    ltv_mae = float(mean_absolute_error(labeled.loc[x_test.index, "y_ltv90"], ltv.predict(x_test)))
    next_mae = float(mean_absolute_error(labeled.loc[x_test.index, "y_next_days"], nxt.predict(x_test)))

    perm = permutation_importance(
        churn, x_test, y_c_test, n_repeats=6, random_state=seed, scoring="roc_auc"
    )
    importance_df = (
        pd.DataFrame({"feature": list(FEATURE_COLUMNS), "importance": perm.importances_mean})
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )

    metrics = {
        "churn_auc": auc,
        "ltv_mae": ltv_mae,
        "next_mae": next_mae,
        "n_train": float(len(x_train)),
        "n_test": float(len(x_test)),
        "churn_rate": float(labeled["y_churn"].mean()),
    }
    return TwinModels(
        churn=churn,
        ltv=ltv,
        next_purchase=nxt,
        feature_names=list(FEATURE_COLUMNS),
        metrics=metrics,
        importances=importance_df,
    )
