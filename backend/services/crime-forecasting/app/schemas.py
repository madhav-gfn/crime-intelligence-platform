from pydantic import BaseModel


class SeriesForecast(BaseModel):
    series: str
    selected_model: str
    backtest_mae: float
    backtest_mape: float | None
    naive_backtest_mae: float
    linear_trend_backtest_mae: float
    moving_average_backtest_mae: float
    last_observed_year: int
    last_observed_value: float
    forecast_2013: float
    forecast_2014: float
    forecast_2015: float


class DistrictForecastBundle(BaseModel):
    state: str
    district: str
    series: list[SeriesForecast]


class DatasetStats(BaseModel):
    total_ncrb_districts: int
    districts_with_complete_2001_2012_history: int
    districts_excluded_incomplete_history: int
    series_forecast: int
    train_years: list[int]
    test_years: list[int]
    forecast_years: list[int]
    model_win_counts: dict[str, int]
    series_where_naive_was_beaten: int
    series_where_naive_was_beaten_pct: float
    mean_backtest_mae_by_model: dict[str, float]


class RankingEntry(BaseModel):
    state: str
    district: str
    last_observed_value: float
    forecast_2015: float
    pct_change: float | None
    selected_model: str
    backtest_mae: float


class RankingResponse(BaseModel):
    series: str
    order: str
    limit: int
    districts: list[RankingEntry]
