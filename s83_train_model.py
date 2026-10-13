"""Section 8.3 - Train and evaluate one regression model.

Model: Ridge regression (linear regression with an L2 penalty).

Why Ridge
    * Hourly consumption is strongly linear in its own history (yesterday,
      last week), which is exactly what a linear model captures.
    * A linear model can follow the slow upward trend in the data, because
      its prediction scales with the lag values. Tree models cannot predict
      beyond the range they saw in training.
    * It has one setting (alpha, the penalty strength), so the comparison of
      configurations is easy to explain.

Shared predictors (identical for every configuration)
    numeric      lag_24h, lag_48h, lag_168h, prev_day_mean
    categorical  hour_of_day, day_of_week, region
Preprocessing (fitted on TRAINING rows only)
    numeric      StandardScaler  (subtract the training mean, divide by the training std)
    categorical  OneHotEncoder   (one 0/1 column per category seen in training)

Procedure
    1. Fit each configuration on the retained training rows (8-14 Sept).
    2. Score each on the validation rows (15-21 Sept): MAE and RMSE.
    3. Select the configuration with the LOWEST validation MAE.
    4. Freeze that fitted model together with its preprocessing: save it to
       disk. It is NOT refitted on validation or test data.
    5. Load the frozen model and produce the 1,680 test predictions.
       Lag values for later test days come from earlier, already completed
       days (they are observed values, not predictions), which is allowed.

Run:  python s83_train_model.py     (after s81_prepare_features.py)
"""

from __future__ import annotations

import time

import joblib
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import forecast_common as fc
from common import RESULTS_DIR, cat_text, finish_log, format_table, start_log

STEP = "8_3_train_model"

# The configurations: same model, same predictors, same rows; only alpha differs.
# A larger alpha shrinks the coefficients more (simpler model, less variance).
CONFIGURATIONS = [
    {"id": "R1", "alpha": 0.1},
    {"id": "R2", "alpha": 1.0},
    {"id": "R3", "alpha": 10.0},
    {"id": "R4", "alpha": 100.0},
]


def build_pipeline(alpha: float) -> Pipeline:
    """Preprocessing and model in ONE object, so fitting the pipeline on the
    training rows fits the scaler and encoder on the training rows only, and
    predicting later reuses exactly those fitted values."""
    preprocessing = ColumnTransformer([
        ("numeric", StandardScaler(), fc.NUMERIC_FEATURES),
        ("categorical", OneHotEncoder(handle_unknown="ignore"), fc.CATEGORICAL_FEATURES),
    ])
    return Pipeline([("preprocessing", preprocessing), ("model", Ridge(alpha=alpha))])


def main() -> None:
    start_log(STEP)
    data = fc.load_dataset()
    usable = fc.usable(data)
    train = data[fc.split_mask(data, "train") & usable]
    validation = data[fc.split_mask(data, "validation") & usable]
    test = data[fc.split_mask(data, "test") & usable].copy()

    print("Model               : Ridge regression (scikit-learn)")
    print(f"Shared predictors   : {', '.join(fc.FEATURES)}")
    print(f"Training rows       : {len(train):,}  ({train['target_hour'].min()} to {train['target_hour'].max()})")
    print(f"Validation rows     : {len(validation):,}  ({validation['target_hour'].min()} to {validation['target_hour'].max()})")
    print(f"Test rows           : {len(test):,}  ({test['target_hour'].min()} to {test['target_hour'].max()})")

    # ---- 1-2. Fit on training, score on validation -----------------------------------
    results, fitted = [], {}
    for config in CONFIGURATIONS:
        started = time.perf_counter()
        pipeline = build_pipeline(config["alpha"]).fit(train[fc.FEATURES], train[fc.TARGET])
        seconds = time.perf_counter() - started
        mae, rmse = fc.metrics(pipeline.predict(validation[fc.FEATURES]), validation[fc.TARGET])
        fitted[config["id"]] = pipeline
        results.append({"id": config["id"], "settings": f"Ridge(alpha={config['alpha']})",
                        "train_rows": len(train), "validation_rows": len(validation),
                        "mae": mae, "rmse": rmse, "fit_seconds": seconds})
        print(f"Training completed  : {config['id']} Ridge(alpha={config['alpha']}) in {seconds:.3f} s at {cat_text()}")

    headers = ["configuration ID", "model settings", "training rows", "validation rows",
               "validation MAE (kWh)", "validation RMSE (kWh)"]
    table = [(r["id"], r["settings"], r["train_rows"], r["validation_rows"], f"{r['mae']:.4f}", f"{r['rmse']:.4f}")
             for r in results]
    print("\n--- Validation comparison ---")
    print(format_table(headers, table))

    # ---- 3-4. Select by lowest validation MAE and freeze -------------------------------
    best = min(results, key=lambda r: r["mae"])
    joblib.dump(fitted[best["id"]], fc.MODEL_FILE)
    print(f"\nSelected configuration: {best['id']} {best['settings']} (lowest validation MAE {best['mae']:.4f} kWh)")
    print(f"Frozen model + preprocessing saved to results/{fc.MODEL_FILE.name} at {cat_text()}")
    print("It is used as saved from here on: no refit on validation or test data.")

    # ---- 5. Test predictions from the frozen model ----------------------------------------
    frozen = joblib.load(fc.MODEL_FILE)
    test["model_kwh"] = frozen.predict(test[fc.FEATURES])
    print(f"\nTest predictions produced: {len(test):,} "
          f"({test['region'].nunique()} regions x {test['target_hour'].dt.normalize().nunique()} days x 24 hours)")
    columns = ["region", "target_hour", "forecast_origin", fc.TARGET, "model_kwh"]
    sample = test[test["region"] == "Region 1"].head(8)[columns].copy()
    sample[fc.TARGET], sample["model_kwh"] = sample[fc.TARGET].round(3), sample["model_kwh"].round(3)
    print("\n--- Sample test predictions ---")
    print(format_table(columns, sample.astype(str).values.tolist()))

    test[["region", "target_hour", fc.TARGET, "model_kwh"]].to_csv(fc.MODEL_PREDICTIONS_FILE, index=False)
    (RESULTS_DIR / "8_3_validation_comparison.md").write_text(
        "# 8.3 Validation comparison\n\nShared predictors: " + ", ".join(fc.FEATURES) + "\n\n"
        + format_table(headers, table, markdown=True)
        + f"\n\nSelected: {best['id']} {best['settings']}\n", encoding="utf-8")
    print(f"\nPredictions saved: results/{fc.MODEL_PREDICTIONS_FILE.name}")
    finish_log(STEP)


if __name__ == "__main__":
    main()
