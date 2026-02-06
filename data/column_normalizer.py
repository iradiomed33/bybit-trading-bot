"""

Нормализация имён колонок индикаторов.


Канонические имена:

- adx: Average Directional Index

- rsi: Relative Strength Index

- atr: Average True Range

- atr_percent: ATR as % of price

- ema_10, ema_20, ema_50, ema_200: Exponential Moving Averages

- sma_10, sma_20, sma_50, sma_200: Simple Moving Averages

- bb_width, bb_percent: Bollinger Bands

- volume_zscore: Volume z-score

- vwap, vwap_distance: VWAP indicators

- obv: On-Balance Volume

- dmp, dmn: Directional indicators (+ and -)

"""


import pandas as pd

import numpy as np

from logger import setup_logger


logger = setup_logger(__name__)


# Канонические имена индикаторов

CANONICAL_INDICATORS = {

    "adx": "adx",

    "rsi": "rsi",

    "atr": "atr",

    "atr_percent": "atr_percent",

    "ema_10": "ema_10",

    "ema_20": "ema_20",

    "ema_50": "ema_50",

    "ema_200": "ema_200",

    "sma_10": "sma_10",

    "sma_20": "sma_20",

    "sma_50": "sma_50",

    "sma_200": "sma_200",

    "bb_width": "bb_width",

    "bb_percent": "bb_percent",

    "volume_zscore": "volume_zscore",

    "volume_sma": "volume_sma",

    "volume_impulse": "volume_impulse",

    "vwap": "vwap",

    "vwap_distance": "vwap_distance",

    "obv": "obv",

    "dmp": "dmp",  # Plus Directional Indicator

    "dmn": "dmn",  # Minus Directional Indicator

    "rsi": "rsi",

}


# Возможные альтернативные имена (для совместимости)

ALIASES = {

    "ADX_14": "adx",

    "ADX": "adx",

    "RSI_14": "rsi",

    "RSI": "rsi",

    "ATR_14": "atr",

    "ATR": "atr",

    "VWAP": "vwap",

    "OBV": "obv",

    "DI+": "dmp",

    "DI-": "dmn",

    "DMP": "dmp",

    "DMN": "dmn",

}


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """

    Нормализовать имена колонок в DataFrame.


    Заменяет старые имена на канонические если они найдены.


    Args:

        df: DataFrame с индикаторами


    Returns:

        DataFrame с нормализованными именами

    """

    df = df.copy()

    renamed = {}

    for col in df.columns:

        if col in ALIASES:

            canonical_name = ALIASES[col]

            if canonical_name not in df.columns:

                df = df.rename(columns={col: canonical_name})

                renamed[col] = canonical_name

                logger.debug(f"Renamed column: {col} → {canonical_name}")

    if renamed:

        logger.info(f"Normalized {len(renamed)} column names: {renamed}")

    return df


def ensure_required_columns(df: pd.DataFrame, required: list = None) -> pd.DataFrame:
    """

    Гарантировать наличие обязательных колонок с дефолт значениями.


    Если колонка отсутствует, добавляется с NaN или дефолт значением.


    Args:

        df: DataFrame

        required: Список обязательных колонок (если None, используются все канонические)


    Returns:

        DataFrame с гарантированными колонками

    """

    if required is None:

        required = list(CANONICAL_INDICATORS.keys())

    df = df.copy()

    missing = []

    for col in required:

        if col not in df.columns:

            # Добавить колонку с NaN (будет заполнена потом)

            df[col] = np.nan

            missing.append(col)

    if missing:

        logger.warning(f"Missing columns {missing} - filled with NaN")

    return df


def get_indicator_value(df: pd.DataFrame, indicator_name: str, default: float = None) -> float:
    """

    Безопасно получить значение индикатора с фолбеком.


    Args:

        df: DataFrame с индикаторами

        indicator_name: Каноническое имя индикатора

        default: Дефолт значение если индикатор не найден


    Returns:

        Значение индикатора или default

    """

    if df is None or df.empty:

        return default

    # Сначала ищем прямое имя

    if indicator_name in df.columns:

        value = df[indicator_name].iloc[-1] if len(df) > 0 else default

        return float(value) if pd.notna(value) else default

    # Потом ищем альтернативные имена

    for alt_name, canonical in ALIASES.items():

        if canonical == indicator_name and alt_name in df.columns:

            value = df[alt_name].iloc[-1] if len(df) > 0 else default

            return float(value) if pd.notna(value) else default

    logger.debug(f"Indicator '{indicator_name}' not found, returning default: {default}")

    return default


def validate_dataframe(df: pd.DataFrame, verbose: bool = False) -> dict:
    """

    Валидировать DataFrame на наличие всех необходимых индикаторов.


    Args:

        df: DataFrame для проверки

        verbose: Выводить ли детальную информацию


    Returns:

        Dict с информацией о наличии индикаторов

    """

    if df is None or df.empty:

        return {"status": "empty", "columns": []}

    status = {

        "status": "ok",

        "total_columns": len(df.columns),

        "canonical_found": [],

        "aliases_found": [],

        "missing": [],

    }

    for canonical, _ in CANONICAL_INDICATORS.items():

        if canonical in df.columns:

            status["canonical_found"].append(canonical)

        elif canonical in [ALIASES.get(col) for col in df.columns]:

            status["aliases_found"].append(canonical)

        else:

            status["missing"].append(canonical)

    if verbose:

        logger.info(f"DataFrame validation: {status}")

    return status
