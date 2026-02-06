# -*- coding: utf-8 -*-

"""

Backtest Metrics Reporter - E2 EPIC


Сравнение результатов бэктестов:

- Metrics для отдельных бэктестов

- Side-by-side сравнение стратегий

- Train vs test сравнение

- Таблицы в формате JSON/CSV

"""


from typing import Dict, Any

from decimal import Decimal

import logging

import json


logger = logging.getLogger(__name__)


class BacktestMetricsReporter:

    """Генератор отчетов по метрикам бэктестов"""

    @staticmethod
    def format_metrics_table(result: Dict[str, Any]) -> "Any":
        """

        Форматировать metrics одного бэктеста в таблицу.


        Args:

            result: Result dict from BacktestRunner.run_backtest()


        Returns:

            DataFrame с основными метриками

        """

        import pandas as pd

        metrics = result["metrics"]

        return pd.DataFrame(

            {

                "Metric": [

                    "Total Trades",

                    "Winning Trades",

                    "Losing Trades",

                    "Win Rate %",

                    "Profit Factor",

                    "Total PnL $",

                    "Avg PnL/Trade $",

                    "Largest Win $",

                    "Largest Loss $",

                    "Expectancy $",

                    "Max Drawdown $",

                    "Max Drawdown %",

                    "Sharpe Ratio",

                    "Sortino Ratio",

                    "Recovery Factor",

                    "SL Hit Rate %",

                    "TP Hit Rate %",

                ],

                "Value": [

                    metrics.total_trades,

                    metrics.winning_trades,

                    metrics.losing_trades,

                    f"{float(metrics.win_rate):.1f}",

                    (

                        f"{float(metrics.profit_factor):.2f}"

                        if metrics.profit_factor != Decimal("inf")

                        else "∞"

                    ),

                    f"${float(metrics.total_pnl):.2f}",

                    f"${float(metrics.avg_pnl_per_trade):.2f}",

                    f"${float(metrics.largest_winning_trade):.2f}",

                    f"${float(metrics.largest_losing_trade):.2f}",

                    f"${float(metrics.expectancy):.2f}",

                    f"${float(metrics.max_drawdown_dollars):.2f}",

                    f"{float(metrics.max_drawdown_percent):.2f}",

                    f"{float(metrics.sharpe_ratio):.2f}",

                    f"{float(metrics.sortino_ratio):.2f}",

                    (

                        f"{float(metrics.recovery_factor):.2f}"

                        if metrics.recovery_factor > 0

                        else "N/A"

                    ),

                    f"{float(metrics.sl_hit_rate):.1f}",

                    f"{float(metrics.tp_hit_rate):.1f}",

                ],

            }

        )

    @staticmethod
    def compare_strategies(results: Dict[str, Dict[str, Any]]) -> "Any":
        """

        Сравнить несколько стратегий side-by-side.


        Args:

            results: Dict[strategy_name, result_dict]


        Returns:

            DataFrame для сравнения

        """

        import pandas as pd

        comparison_data = []

        for strategy_name, result in results.items():

            metrics = result["metrics"]

            simulator = result["simulator"]

            comparison_data.append(

                {

                    "Strategy": strategy_name,

                    "Trades": metrics.total_trades,

                    "Win %": f"{float(metrics.win_rate):.1f}",

                    "PnL $": f"${float(metrics.total_pnl):.2f}",

                    "Profit Factor": (

                        f"{float(metrics.profit_factor):.2f}"

                        if metrics.profit_factor != Decimal("inf")

                        else "∞"

                    ),

                    "Sharpe": f"{float(metrics.sharpe_ratio):.2f}",

                    "Max DD %": f"{float(metrics.max_drawdown_percent):.2f}",

                    "ROI %": f"{float((metrics.total_pnl / simulator.initial_balance * 100)):.1f}",

                }

            )

        return pd.DataFrame(comparison_data)

    @staticmethod
    def compare_train_test(train_result: Dict[str, Any], test_result: Dict[str, Any]) -> "Any":
        """

        Сравнить train vs test результаты для одной стратегии.


        Args:

            train_result: Result dict для train

            test_result: Result dict для test


        Returns:

            DataFrame для сравнения

        """

        import pandas as pd

        train_metrics = train_result["metrics"]

        test_metrics = test_result["metrics"]

        train_roi = train_metrics.total_pnl / train_result["simulator"].initial_balance * 100

        test_roi = test_metrics.total_pnl / test_result["simulator"].initial_balance * 100

        return pd.DataFrame(

            {

                "Metric": [

                    "Total Trades",

                    "Winning Trades",

                    "Win Rate %",

                    "Total PnL $",

                    "ROI %",

                    "Profit Factor",

                    "Sharpe Ratio",

                    "Max Drawdown %",

                    "Sortino Ratio",

                ],

                "Train": [

                    train_metrics.total_trades,

                    train_metrics.winning_trades,

                    f"{float(train_metrics.win_rate):.1f}",

                    f"${float(train_metrics.total_pnl):.2f}",

                    f"{float(train_roi):.1f}",

                    (

                        f"{float(train_metrics.profit_factor):.2f}"

                        if train_metrics.profit_factor != Decimal("inf")

                        else "∞"

                    ),

                    f"{float(train_metrics.sharpe_ratio):.2f}",

                    f"{float(train_metrics.max_drawdown_percent):.2f}",

                    f"{float(train_metrics.sortino_ratio):.2f}",

                ],

                "Test": [

                    test_metrics.total_trades,

                    test_metrics.winning_trades,

                    f"{float(test_metrics.win_rate):.1f}",

                    f"${float(test_metrics.total_pnl):.2f}",

                    f"{float(test_roi):.1f}",

                    (

                        f"{float(test_metrics.profit_factor):.2f}"

                        if test_metrics.profit_factor != Decimal("inf")

                        else "∞"

                    ),

                    f"{float(test_metrics.sharpe_ratio):.2f}",

                    f"{float(test_metrics.max_drawdown_percent):.2f}",

                    f"{float(test_metrics.sortino_ratio):.2f}",

                ],

            }

        )

    @staticmethod
    def generate_html_report(

        results: Dict[str, Dict[str, Any]],

        output_path: str = "backtest_report.html",

    ) -> str:
        """

        Генерировать HTML отчет.


        Args:

            results: Results dict (может быть из одного или нескольких бэктестов)

            output_path: Путь для сохранения HTML


        Returns:

            HTML string

        """

        html_parts = [

            "<!DOCTYPE html>",

            "<html>",

            "<head>",

            "<meta charset='utf-8'>",

            "<title>Backtest Report</title>",

            "<style>",

            "body { font-family: Arial, sans-serif; margin: 20px; }",

            "table { border-collapse: collapse; width: 100%; margin: 20px 0; }",

            "th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }",

            "th { background-color: #4CAF50; color: white; }",

            "tr:nth-child(even) { background-color: #f2f2f2; }",

            ".positive { color: green; font-weight: bold; }",

            ".negative { color: red; font-weight: bold; }",

            "h1, h2 { color: #333; }",

            "</style>",

            "</head>",

            "<body>",

            "<h1>Backtest Report</h1>",

        ]

        # Добавить таблицу сравнения стратегий

        if len(results) > 1:

            html_parts.append("<h2>Strategy Comparison</h2>")

            comparison_df = BacktestMetricsReporter.compare_strategies(results)

            html_parts.append(comparison_df.to_html(index=False))

        # Добавить детальные метрики для каждой стратегии

        for strategy_name, result in results.items():

            html_parts.append(f"<h2>{strategy_name}</h2>")

            # Basic info

            html_parts.append("<p>")

            html_parts.append(f"Period: {result['start_date']} to {result['end_date']}<br>")

            html_parts.append(f"Candles: {result['candles_count']}<br>")

            html_parts.append(

                f"Price: ${float(result['start_price']):.2f} → ${float(result['end_price']):.2f}"

            )

            html_parts.append("</p>")

            # Metrics table

            metrics_df = BacktestMetricsReporter.format_metrics_table(result)

            html_parts.append(metrics_df.to_html(index=False))

        html_parts.extend(

            [

                "</body>",

                "</html>",

            ]

        )

        html_content = "\n".join(html_parts)

        # Сохранить файл

        with open(output_path, "w", encoding="utf-8") as f:

            f.write(html_content)

        logger.info(f"HTML report saved to {output_path}")

        return html_content

    @staticmethod
    def export_to_json(result: Dict[str, Any], output_path: str) -> str:
        """

        Экспортировать результаты в JSON.


        Args:

            result: Result dict

            output_path: Путь для сохранения


        Returns:

            JSON string

        """

        # Конвертировать metrics объект

        metrics = result["metrics"]

        metrics_dict = {

            "total_trades": metrics.total_trades,

            "winning_trades": metrics.winning_trades,

            "losing_trades": metrics.losing_trades,

            "win_rate_percent": float(metrics.win_rate),

            "profit_factor": (

                float(metrics.profit_factor) if metrics.profit_factor != Decimal("inf") else None

            ),

            "total_pnl": float(metrics.total_pnl),

            "avg_pnl_per_trade": float(metrics.avg_pnl_per_trade),

            "largest_winning_trade": float(metrics.largest_winning_trade),

            "largest_losing_trade": float(metrics.largest_losing_trade),

            "expectancy": float(metrics.expectancy),

            "max_drawdown_dollars": float(metrics.max_drawdown_dollars),

            "max_drawdown_percent": float(metrics.max_drawdown_percent),

            "sharpe_ratio": float(metrics.sharpe_ratio),

            "sortino_ratio": float(metrics.sortino_ratio),

            "recovery_factor": (

                float(metrics.recovery_factor) if metrics.recovery_factor > 0 else None

            ),

        }

        # Конвертировать trades

        trades_list = []

        for trade in result["trades"]:

            trades_list.append(

                {

                    "entry_price": float(trade.entry_price),

                    "exit_price": float(trade.exit_price),

                    "qty": float(trade.entry_qty),

                    "pnl": float(trade.pnl),

                    "pnl_after_commission": float(trade.pnl_after_commission),

                    "roi_percent": float(trade.roi_percent),

                    "was_sl_hit": trade.was_sl_hit,

                    "was_tp_hit": trade.was_tp_hit,

                }

            )

        output_dict = {

            "name": result.get("name", "backtest"),

            "start_date": str(result["start_date"]),

            "end_date": str(result["end_date"]),

            "candles_count": result["candles_count"],

            "trades_count": result["trades_count"],

            "metrics": metrics_dict,

            "trades": trades_list,

        }

        json_str = json.dumps(output_dict, indent=2)

        with open(output_path, "w") as f:

            f.write(json_str)

        logger.info(f"Results exported to {output_path}")

        return json_str

    @staticmethod
    def print_summary(result: Dict[str, Any]) -> None:
        """

        Напечатать summary в консоль.


        Args:

            result: Result dict

        """

        metrics = result["metrics"]

        simulator = result["simulator"]

        print("\n" + "=" * 60)

        print(f"Backtest: {result.get('name', 'backtest')}")

        print("=" * 60)

        print(f"Period: {result['start_date']} to {result['end_date']}")

        print(f"Candles: {result['candles_count']}")

        print(f"Price: ${float(result['start_price']):.2f} → ${float(result['end_price']):.2f}")

        print("-" * 60)

        print(f"Total Trades: {metrics.total_trades}")

        print(f"Winning: {metrics.winning_trades} ({float(metrics.win_rate):.1f}%)")

        print(f"Losing: {metrics.losing_trades}")

        print(

            f"Profit Factor: {float(metrics.profit_factor):.2f}"

            if metrics.profit_factor != Decimal("inf")

            else "Profit Factor: ∞"

        )

        print("-" * 60)

        print(f"Initial Balance: ${float(simulator.initial_balance):.2f}")

        print(f"Final Equity: ${float(simulator.get_equity()):.2f}")

        print(f"Total PnL: ${float(metrics.total_pnl):.2f}")

        print(f"ROI: {float(metrics.total_pnl / simulator.initial_balance * 100):.2f}%")

        print("-" * 60)

        print(

            f"Max Drawdown: ${float(metrics.max_drawdown_dollars):.2f} ({float(metrics.max_drawdown_percent):.2f}%)"

        )

        print(f"Sharpe Ratio: {float(metrics.sharpe_ratio):.2f}")

        print(f"Sortino Ratio: {float(metrics.sortino_ratio):.2f}")

        print(

            f"Recovery Factor: {float(metrics.recovery_factor):.2f}"

            if metrics.recovery_factor > 0

            else "Recovery Factor: N/A"

        )

        print("=" * 60 + "\n")
