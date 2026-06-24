import argparse
import datetime as dt
import tempfile
import unittest
from unittest import mock

import stock_analyst


class StockAnalystTests(unittest.TestCase):
    def test_specific_symbols_do_not_include_default_watchlist(self):
        args = argparse.Namespace(watchlist=None, symbols=["aapl", "MSFT", "aapl"])

        self.assertEqual(stock_analyst.resolve_symbols(args), ["AAPL", "MSFT"])

    def test_empty_symbols_use_market_universe_path(self):
        args = argparse.Namespace(watchlist=None, symbols=[])

        self.assertEqual(stock_analyst.resolve_symbols(args), [])

    def test_momentum_rewards_positive_trends_and_sma_alignment(self):
        score = stock_analyst.score_momentum(
            return_1y=0.2,
            return_6m=0.1,
            return_3m=0.05,
            sma_50=110,
            sma_200=100,
            price=120,
        )

        self.assertGreater(score, 85)

    def test_risk_penalizes_high_volatility_and_drawdown(self):
        low_risk = stock_analyst.score_risk(volatility=0.12, drawdown=-0.05, beta=0.8)
        high_risk = stock_analyst.score_risk(volatility=0.45, drawdown=-0.35, beta=1.7)

        self.assertGreater(low_risk, high_risk)

    def test_format_duration(self):
        self.assertEqual(stock_analyst.format_duration(42), "42s")
        self.assertEqual(stock_analyst.format_duration(125), "2m 5s")
        self.assertEqual(stock_analyst.format_duration(3720), "1h 2m")

    def test_score_grade(self):
        self.assertEqual(stock_analyst.score_grade(90), "A")
        self.assertEqual(stock_analyst.score_grade(70), "B")
        self.assertEqual(stock_analyst.score_grade(55), "C")
        self.assertEqual(stock_analyst.score_grade(40), "D")
        self.assertEqual(stock_analyst.score_grade(None), "-")

    def test_estimate_hold_window(self):
        hold = stock_analyst.estimate_hold_window("reversal", "CALL", 90, -0.05, -0.12, 0.25)

        self.assertIn("trading days", hold)

    def test_estimate_entry_plan_is_trigger_based(self):
        plan = stock_analyst.estimate_entry_plan(
            "reversal",
            "CALL",
            80,
            -0.01,
            -0.05,
            100,
            [100, 101, 102],
            [97, 98, 99],
            [99, 100, 101],
        )

        self.assertIn("early CALL reversal", plan)
        self.assertIn("Starter zone", plan)
        self.assertIn("add/confirmation", plan)
        self.assertIn("quick higher-low", plan)

    def test_catalyst_scoring_is_direction_aware(self):
        news = [
            stock_analyst.NewsItem("Chip maker surges after AI data center deal", "", ""),
            stock_analyst.NewsItem("Analysts raise target after strong demand", "", ""),
        ]

        call_assessment = stock_analyst.assess_catalysts(news, "CALL")
        put_assessment = stock_analyst.assess_catalysts(news, "PUT")

        self.assertGreater(call_assessment.score, put_assessment.score)
        self.assertIn("catalyst", call_assessment.label.lower())

    def test_geopolitical_risk_can_support_put_setup(self):
        news = [
            stock_analyst.NewsItem("Shares fall as China tariffs and export controls weigh on outlook", "", ""),
        ]

        assessment = stock_analyst.assess_catalysts(news, "PUT")

        self.assertGreaterEqual(assessment.score, 70)
        self.assertTrue(any("geopolitical" in note for note in assessment.notes))

    def test_oil_shock_penalizes_non_energy_calls(self):
        shock_news = [
            stock_analyst.NewsItem("Oil jumps as Iran shuts Strait of Hormuz and shipping reroutes", "", "", "Reuters"),
        ]
        item = stock_analyst.Analysis(
            symbol="GOOGL",
            name="Alphabet",
            price=100,
            score=70,
            rating="Candidate",
            momentum_score=70,
            value_score=50,
            risk_score=60,
            yield_score=40,
            return_1y=None,
            return_6m=None,
            return_3m=None,
            volatility=None,
            max_drawdown=None,
            sharpe_like=None,
            rsi=None,
            sma_50=None,
            sma_200=None,
            market_cap=None,
            pe=None,
            dividend_yield=None,
            beta=None,
            notes=[],
            news=[],
            macro_news=shock_news,
            setup_direction="CALL",
        )
        base = stock_analyst.CatalystAssessment(70, "Catalyst support", [])
        shock = stock_analyst.macro_oil_shock(shock_news)

        adjusted = stock_analyst.macro_adjusted_catalyst_score(item, base, shock)

        self.assertTrue(shock["active"])
        self.assertLess(adjusted.score, base.score)
        self.assertTrue(any("risk-off for normal calls" in note for note in adjusted.notes))
        self.assertIn("skeptical of normal CALL setups", stock_analyst.oil_shock_trade_warning(item))
        brief = stock_analyst.TradeBrief(
            thesis="Test",
            pattern="Trend",
            pattern_status="forming",
            confirmation_level=101,
            measured_move=110,
            invalidation=95,
            stop_loss=95,
            target_1=105,
            target_2=110,
            target_3=115,
            risk_reward=1.5,
            market_structure="mixed",
            timeframe_supporting=[],
            timeframe_opposing=[],
            alignment_score=60,
            indicator_analysis="mixed",
            volume_analysis="mixed",
            relative_strength="mixed",
            support_resistance="mixed",
            volume_profile="mixed",
            liquidity_analysis="liquid",
            options_flow="unknown",
            order_flow="unknown",
            catalyst_analysis="mixed",
            market_environment="risk-off",
            event_risk="high",
            bull_case="",
            base_case="",
            bear_case="",
            confidence_score=60,
            setup_grade="B",
            take_reasons=[],
            avoid_reasons=[],
            final_recommendation="Conditional",
        )
        self.assertEqual(
            stock_analyst.analyst_stance(item, brief),
            "Pass for now - Real-money veto",
        )
        judgment = stock_analyst.real_money_trader_judgment(item, brief)
        self.assertTrue(judgment["veto"])
        self.assertIn("risk-off tape", " ".join(judgment["reasons"]))
        banner = stock_analyst.macro_report_banner([item])
        self.assertIn("Critical macro override", banner)
        self.assertIn("risk-off oil shock", banner)

    def test_expanded_news_summary_explains_major_catalysts(self):
        item = stock_analyst.Analysis(
            symbol="TEST",
            name="Test Co",
            price=100,
            score=70,
            rating="Candidate",
            momentum_score=70,
            value_score=50,
            risk_score=60,
            yield_score=40,
            return_1y=None,
            return_6m=None,
            return_3m=None,
            volatility=None,
            max_drawdown=None,
            sharpe_like=None,
            rsi=None,
            sma_50=None,
            sma_200=None,
            market_cap=None,
            pe=None,
            dividend_yield=None,
            beta=None,
            notes=[],
            news=[
                stock_analyst.NewsItem("Test Co wins AI data center deal after upgrade", "", ""),
                stock_analyst.NewsItem("Analyst raises target on strong demand", "", ""),
            ],
            setup_direction="CALL",
            entry_plan="Wait for price to reclaim prior close.",
            catalyst_score=92,
            catalyst_label="Strong catalyst alignment",
        )

        summary = stock_analyst.expanded_news_summary(item)

        self.assertIn("Catalyst summary", summary)
        self.assertIn("Test Co wins AI data center deal", summary)
        self.assertIn("My read", summary)
        self.assertIn("future revenue", summary)
        self.assertNotIn("The important items are", summary)
        self.assertNotIn("The first item matters because", summary)
        self.assertNotIn("Chart context", summary)
        self.assertNotIn("Net read", summary)
        self.assertNotIn("meaningful news cluster", summary)
        self.assertNotIn("strongest source text", summary)
        self.assertNotIn("Entry timing remains trigger-based", summary)

    def test_major_news_filter_removes_low_value_headlines(self):
        news = [
            stock_analyst.NewsItem("3 Best Stocks to Buy According to Analysts", "", ""),
            stock_analyst.NewsItem("Company wins major defense contract", "", ""),
        ]

        major = stock_analyst.major_news_items(news)

        self.assertEqual(len(major), 1)
        self.assertIn("contract", major[0].title)

    def test_expanded_news_summary_includes_macro_news(self):
        item = stock_analyst.Analysis(
            symbol="XOM",
            name="Oil Co",
            price=100,
            score=70,
            rating="Candidate",
            momentum_score=70,
            value_score=50,
            risk_score=60,
            yield_score=40,
            return_1y=None,
            return_6m=None,
            return_3m=None,
            volatility=None,
            max_drawdown=None,
            sharpe_like=None,
            rsi=None,
            sma_50=None,
            sma_200=None,
            market_cap=None,
            pe=None,
            dividend_yield=None,
            beta=None,
            notes=[],
            news=[],
            macro_news=[
                stock_analyst.NewsItem("Oil jumps as Middle East conflict escalates", "", ""),
            ],
            setup_direction="CALL",
            entry_plan="Wait for confirmation.",
            catalyst_score=72,
            catalyst_label="Catalyst support",
        )

        summary = stock_analyst.expanded_news_summary(item)

        self.assertIn("Oil jumps as Middle East conflict escalates", summary)
        self.assertIn("My read", summary)
        self.assertIn("oil inventory", summary)
        self.assertNotIn("The important items are", summary)
        self.assertNotIn("The first item matters because", summary)
        self.assertNotIn("Chart context", summary)
        self.assertNotIn("news matters because", summary)

    def test_relevant_macro_news_excludes_unrelated_roundups(self):
        news = [
            stock_analyst.NewsItem("S&P 500, Nasdaq, Dow End Higher On SpaceX Debut - XOM In Focus", "", ""),
            stock_analyst.NewsItem("Oil jumps as Middle East conflict escalates", "", ""),
        ]

        relevant = stock_analyst.relevant_macro_news(news, "XOM")

        self.assertEqual(len(relevant), 1)
        self.assertIn("Oil jumps", relevant[0].title)

    def test_macro_summary_explains_financial_context(self):
        item = stock_analyst.Analysis(
            symbol="GS",
            name="Goldman Sachs",
            price=100,
            score=70,
            rating="Candidate",
            momentum_score=70,
            value_score=50,
            risk_score=60,
            yield_score=40,
            return_1y=None,
            return_6m=None,
            return_3m=None,
            volatility=None,
            max_drawdown=None,
            sharpe_like=None,
            rsi=None,
            sma_50=None,
            sma_200=None,
            market_cap=None,
            pe=None,
            dividend_yield=None,
            beta=None,
            notes=[],
            news=[],
            macro_news=[
                stock_analyst.NewsItem("SpaceX IPO boosts dealmaking sentiment as inflation and Middle East risk linger", "", ""),
            ],
            setup_direction="PUT",
            entry_plan="Wait for rejection.",
        )

        summary = stock_analyst.expanded_news_summary(item)

        self.assertIn("SpaceX IPO boosts dealmaking sentiment", summary)
        self.assertIn("underwriting", summary)
        self.assertIn("advisory revenue", summary)
        self.assertNotIn("Chart context", summary)
        self.assertNotIn("specifically deal, contract", summary)

    def test_choose_expiration_date_prefers_range(self):
        today = dt.datetime.now().astimezone().date()
        dates = [
            (today + dt.timedelta(days=7)).isoformat(),
            (today + dt.timedelta(days=28)).isoformat(),
            (today + dt.timedelta(days=60)).isoformat(),
        ]

        self.assertEqual(
            stock_analyst.choose_expiration_date(dates, 21, 45),
            today + dt.timedelta(days=28),
        )

    def test_parse_nasdaq_expiration(self):
        row = {"expiryDate": "July 03, 2026"}

        self.assertEqual(stock_analyst.parse_nasdaq_expiration(row), dt.date(2026, 7, 3))

    def test_parse_nasdaq_expiration_without_year(self):
        row = {"expiryDate": "Jun 12"}

        self.assertIsNotNone(stock_analyst.parse_nasdaq_expiration(row))

    def test_parse_market_number(self):
        self.assertEqual(stock_analyst.parse_market_number("$1,234.50"), 1234.5)
        self.assertIsNone(stock_analyst.parse_market_number("--"))

    def test_single_flag_enables_on_demand_for_explicit_symbols(self):
        args = stock_analyst.parse_args(["NVDA", "--single"])

        self.assertTrue(stock_analyst.on_demand_enabled(args))

    def test_single_flag_without_symbol_does_not_force_market_scan(self):
        args = stock_analyst.parse_args(["--single"])

        self.assertFalse(stock_analyst.on_demand_enabled(args))

    def test_serve_flag_is_parsed(self):
        args = stock_analyst.parse_args(["--serve"])

        self.assertTrue(args.serve)
        self.assertEqual(args.port, 8765)

    def test_on_demand_symbol_validation(self):
        self.assertEqual(stock_analyst.normalize_on_demand_symbol("brk.b"), "BRK.B")
        with self.assertRaises(ValueError):
            stock_analyst.normalize_on_demand_symbol("NVDA;rm")

    def test_dashboard_html_exposes_app_controls(self):
        document = stock_analyst.report_dashboard_html()

        self.assertIn("Atlas", document)
        self.assertIn("/api/scan", document)
        self.assertIn("/stock_report.html", document)
        self.assertIn("/atlas_ai_wordmark.jpg", document)

    def test_app_command_builders_use_expected_outputs(self):
        script = stock_analyst.Path("/tmp/stock_analyst.py")

        scan_command = stock_analyst.scanner_command(script, "stock_report.html")
        single_command = stock_analyst.on_demand_command(script, "NVDA", "on_demand_report.html")

        self.assertIn("stock_report.html", scan_command)
        self.assertIn("on_demand_report.html", single_command)
        self.assertIn("--single", single_command)
        self.assertIn("NVDA", single_command)

    def test_report_header_omits_old_logo(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = stock_analyst.Path(temp_dir) / "stock_report.html"

            stock_analyst.write_report([], output, "balanced", [])

            document = output.read_text()
        self.assertIn('class="report-hero"', document)
        self.assertNotIn("stock_analyst_logo.jpg", document)
        self.assertNotIn("Stock Analyst logo", document)
        self.assertNotIn("On-demand ticker", document)
        self.assertNotIn("tickerInput", document)
        self.assertIn("collapseAll", document)
        self.assertIn("expandAll", document)
        self.assertNotIn("searchBox", document)
        self.assertNotIn("gradeFilter", document)
        self.assertNotIn("directionFilter", document)
        self.assertNotIn("refreshReport", document)
        self.assertNotIn("resetFilters", document)

    def test_target_profit_levels_include_runner_goals(self):
        item = stock_analyst.Analysis(
            symbol="TEST",
            name="Test Co",
            price=100,
            score=70,
            rating="Candidate",
            momentum_score=70,
            value_score=50,
            risk_score=60,
            yield_score=40,
            return_1y=None,
            return_6m=None,
            return_3m=None,
            volatility=None,
            max_drawdown=None,
            sharpe_like=None,
            rsi=None,
            sma_50=None,
            sma_200=None,
            market_cap=None,
            pe=None,
            dividend_yield=None,
            beta=None,
            notes=[],
            news=[],
            setup_direction="CALL",
            chart_highs=[101, 102, 103, 104, 105],
            chart_lows=[99, 98, 99, 100, 101],
            chart_closes=[100, 101, 102, 103, 104],
        )

        targets = stock_analyst.format_target_profit_levels(item)

        self.assertIn("Minimum $", targets)
        self.assertIn("+20%", targets)
        self.assertIn("T2 $", targets)
        self.assertIn("Runner $", targets)
        self.assertIn("+100%", targets)

    def test_target_profit_levels_use_option_gain_target_when_available(self):
        item = stock_analyst.Analysis(
            symbol="TEST",
            name="Test Co",
            price=100,
            score=70,
            rating="Candidate",
            momentum_score=70,
            value_score=50,
            risk_score=60,
            yield_score=40,
            return_1y=None,
            return_6m=None,
            return_3m=None,
            volatility=None,
            max_drawdown=None,
            sharpe_like=None,
            rsi=None,
            sma_50=None,
            sma_200=None,
            market_cap=None,
            pe=None,
            dividend_yield=None,
            beta=None,
            notes=[],
            news=[],
            setup_direction="CALL",
            chart_highs=[100.5, 101.0, 101.2, 101.4, 101.5],
            chart_lows=[99.5, 99.8, 100.0, 100.2, 100.4],
            chart_closes=[100, 100.2, 100.4, 100.6, 100.8],
            option=stock_analyst.OptionContract(
                contract_symbol="TEST260626C00100000",
                side="CALL",
                strike=100,
                expiration=dt.date(2026, 6, 26),
                bid=4.0,
                ask=5.0,
                last_price=None,
                volume=None,
                open_interest=None,
                implied_volatility=None,
            ),
        )

        first_target = stock_analyst.target_profit_levels(item)[0]

        self.assertEqual(first_target[0], "Minimum")
        self.assertGreater(first_target[1], 101.8)

    def test_option_trade_plan_uses_short_swing_rules(self):
        item = stock_analyst.Analysis(
            symbol="TEST",
            name="Test Co",
            price=100,
            score=70,
            rating="Candidate",
            momentum_score=70,
            value_score=50,
            risk_score=60,
            yield_score=40,
            return_1y=None,
            return_6m=None,
            return_3m=None,
            volatility=None,
            max_drawdown=None,
            sharpe_like=None,
            rsi=None,
            sma_50=None,
            sma_200=None,
            market_cap=None,
            pe=None,
            dividend_yield=None,
            beta=None,
            notes=[],
            news=[],
            setup_direction="CALL",
            chart_highs=[101, 102, 103, 104, 105],
            chart_lows=[99, 98, 99, 100, 101],
            chart_closes=[100, 101, 102, 103, 104],
        )

        plan = stock_analyst.option_trade_plan(item)

        self.assertIn("Long CALL only", plan)
        self.assertIn("No 0DTE", plan)
        self.assertIn("+20%", plan)
        self.assertIn("-25%", plan)

    def test_options_opportunity_score_flags_unavailable_institutional_data(self):
        item = stock_analyst.Analysis(
            symbol="TEST",
            name="Test Co",
            price=100,
            score=70,
            rating="Candidate",
            momentum_score=70,
            value_score=50,
            risk_score=60,
            yield_score=40,
            return_1y=None,
            return_6m=None,
            return_3m=0.08,
            volatility=0.32,
            max_drawdown=None,
            sharpe_like=None,
            rsi=55,
            sma_50=95,
            sma_200=90,
            market_cap=None,
            pe=None,
            dividend_yield=None,
            beta=None,
            notes=[],
            news=[],
            setup_score=78,
            setup_notes=["breakout", "volume expansion"],
            return_20d=0.06,
            volume_ratio=1.4,
            setup_direction="CALL",
            catalyst_score=72,
            catalyst_label="Catalyst support",
        )

        score = stock_analyst.build_options_opportunity_score(item)

        self.assertGreater(score.call_score, score.put_score)
        self.assertTrue(any("Options flow" in item for item in score.missing_data))
        self.assertTrue(any("Dealer positioning" in item for item in score.missing_data))
        self.assertIn("available data only", score.summary)

    def test_earnings_iv_inflation_reduces_directional_option_quality(self):
        option = stock_analyst.OptionContract(
            contract_symbol="TEST260717C00100000",
            side="CALL",
            strike=100,
            expiration=dt.datetime.now().astimezone().date() + dt.timedelta(days=24),
            bid=4.8,
            ask=5.2,
            last_price=5.0,
            volume=1500,
            open_interest=2000,
            implied_volatility=1.35,
        )
        item = stock_analyst.Analysis(
            symbol="TEST",
            name="Test Co",
            price=100,
            score=70,
            rating="Candidate",
            momentum_score=70,
            value_score=50,
            risk_score=60,
            yield_score=40,
            return_1y=None,
            return_6m=None,
            return_3m=0.04,
            volatility=0.35,
            max_drawdown=None,
            sharpe_like=None,
            rsi=55,
            sma_50=95,
            sma_200=90,
            market_cap=None,
            pe=None,
            dividend_yield=None,
            beta=None,
            notes=[],
            news=[stock_analyst.NewsItem("Test Co reports earnings next week", "", "")],
            setup_score=78,
            setup_notes=["breakout", "volume expansion"],
            return_20d=0.05,
            volume_ratio=1.3,
            setup_direction="CALL",
            option=option,
            catalyst_score=70,
        )

        _score, missing, risks = stock_analyst.option_chain_quality(option, item)

        self.assertTrue(any("Earnings/IV inflation" in risk for risk in risks))
        self.assertNotIn("Live implied volatility for earnings-IV check", missing)

    def test_sector_relative_weakness_reduces_bullish_confidence(self):
        item = stock_analyst.Analysis(
            symbol="NVDA",
            name="NVIDIA Corporation",
            price=100,
            score=70,
            rating="Candidate",
            momentum_score=70,
            value_score=50,
            risk_score=60,
            yield_score=40,
            return_1y=None,
            return_6m=None,
            return_3m=0.10,
            volatility=0.30,
            max_drawdown=None,
            sharpe_like=None,
            rsi=58,
            sma_50=96,
            sma_200=88,
            market_cap=None,
            pe=None,
            dividend_yield=None,
            beta=None,
            notes=[],
            news=[],
            setup_score=80,
            setup_notes=["breakout"],
            return_20d=-0.10,
            volume_ratio=1.2,
            setup_direction="CALL",
            catalyst_score=70,
        )
        sector_series = stock_analyst.PriceSeries(
            symbol="SMH",
            dates=[],
            opens=[],
            highs=[],
            lows=[],
            closes=[100.0] * 59 + [94.0],
            volumes=[],
        )

        with mock.patch("stock_analyst.fetch_price_series", return_value=sector_series):
            adjustment, _bullish, bearish, risks = stock_analyst.sector_relative_context(item)

        self.assertLess(adjustment, 0)
        self.assertTrue(any("SMH sector tape is weak" in risk for risk in risks))
        self.assertTrue(any("underperforming SMH" in factor for factor in bearish))

    def test_bad_contract_quality_penalizes_real_money_judgment(self):
        option = stock_analyst.OptionContract(
            contract_symbol="TEST260626C00130000",
            side="CALL",
            strike=130,
            expiration=dt.datetime.now().astimezone().date() + dt.timedelta(days=3),
            bid=0.40,
            ask=0.80,
            last_price=0.60,
            volume=5,
            open_interest=12,
            implied_volatility=1.4,
        )
        item = stock_analyst.Analysis(
            symbol="TEST",
            name="Test Co",
            price=100,
            score=70,
            rating="Candidate",
            momentum_score=70,
            value_score=50,
            risk_score=60,
            yield_score=40,
            return_1y=None,
            return_6m=None,
            return_3m=0.08,
            volatility=0.32,
            max_drawdown=None,
            sharpe_like=None,
            rsi=55,
            sma_50=95,
            sma_200=90,
            market_cap=None,
            pe=None,
            dividend_yield=None,
            beta=None,
            notes=[],
            news=[],
            setup_score=82,
            setup_notes=["breakout", "volume expansion"],
            return_20d=0.06,
            volume_ratio=1.4,
            setup_direction="CALL",
            option=option,
            catalyst_score=78,
        )
        brief = stock_analyst.build_trade_brief(item, {"available": False, "label": "test"})

        judgment = stock_analyst.real_money_trader_judgment(item, brief)

        self.assertTrue(any("contract quality is poor" in reason for reason in judgment["reasons"]))

    def test_tradingview_chart_url_uses_exchange_prefix(self):
        self.assertIn("NASDAQ%3AMSFT", stock_analyst.tradingview_chart_url("MSFT"))
        self.assertIn("NYSE%3AXOM", stock_analyst.tradingview_chart_url("XOM"))

    def test_display_company_name_uses_known_fallback(self):
        self.assertEqual(stock_analyst.display_company_name("CVX", "CVX"), "Chevron Corporation")
        self.assertEqual(stock_analyst.display_company_name("MS", ""), "Morgan Stanley")
        self.assertEqual(stock_analyst.display_company_name("TEST", "Test Co"), "Test Co")

    def test_detail_panel_escapes_html(self):
        item = stock_analyst.Analysis(
            symbol="BAD",
            name="<script>",
            price=10,
            score=50,
            rating="Watchlist",
            momentum_score=50,
            value_score=50,
            risk_score=50,
            yield_score=50,
            return_1y=None,
            return_6m=None,
            return_3m=None,
            volatility=None,
            max_drawdown=None,
            sharpe_like=None,
            rsi=None,
            sma_50=None,
            sma_200=None,
            market_cap=None,
            pe=None,
            dividend_yield=None,
            beta=None,
            notes=["<b>unsafe</b>"],
            news=[],
            average_dollar_volume=None,
        )

        row = stock_analyst.report_block(1, item)
        secondary = stock_analyst.secondary_analysis_html(item)

        self.assertIn('class="summary-company"', row)
        self.assertIn('class="setup-card is-collapsed"', row)
        self.assertIn('class="toggle-card">Expand</button>', row)
        self.assertNotIn('class="theme-panel" open', row)
        self.assertIn("&lt;script&gt;", row)
        self.assertIn("&lt;b&gt;unsafe&lt;/b&gt;", secondary)

    def test_filters_reject_low_price_and_downtrend(self):
        args = argparse.Namespace(
            mode="invest",
            min_price=5,
            min_1y_return=-0.05,
            min_6m_return=-0.05,
            max_volatility=0.55,
            max_drawdown=0.35,
            require_uptrend=True,
            exclude_overbought=True,
            min_dollar_volume=5_000_000,
        )
        item = stock_analyst.Analysis(
            symbol="TEST",
            name="Test Co",
            price=4,
            score=70,
            rating="Candidate",
            momentum_score=70,
            value_score=50,
            risk_score=70,
            yield_score=40,
            return_1y=0.2,
            return_6m=0.1,
            return_3m=0.05,
            volatility=0.2,
            max_drawdown=-0.1,
            sharpe_like=None,
            rsi=55,
            sma_50=10,
            sma_200=9,
            market_cap=None,
            pe=None,
            dividend_yield=None,
            beta=None,
            notes=[],
            news=[],
            average_dollar_volume=10_000_000,
            setup_score=60,
            setup_label="B setup",
            setup_notes=[],
            return_1d=0.01,
            return_5d=0.05,
            return_20d=0.1,
            volume_ratio=1.5,
        )

        self.assertFalse(stock_analyst.passes_filters(item, args))

    def test_trade_filters_require_setup_strength(self):
        args = argparse.Namespace(
            mode="trade",
            strategy="breakout",
            direction="both",
            min_price=5,
            min_dollar_volume=5_000_000,
            min_setup_score=70,
            min_volume_ratio=1.2,
            min_20d_return=0.03,
            trade_require_uptrend=False,
        )
        item = stock_analyst.Analysis(
            symbol="TEST",
            name="Test Co",
            price=25,
            score=55,
            rating="Watchlist",
            momentum_score=50,
            value_score=50,
            risk_score=50,
            yield_score=50,
            return_1y=0.1,
            return_6m=0.05,
            return_3m=0.02,
            volatility=0.3,
            max_drawdown=-0.12,
            sharpe_like=None,
            rsi=62,
            sma_50=20,
            sma_200=18,
            market_cap=None,
            pe=None,
            dividend_yield=None,
            beta=None,
            notes=[],
            news=[],
            average_dollar_volume=10_000_000,
            setup_score=65,
            setup_label="B setup",
            setup_notes=[],
            return_1d=0.01,
            return_5d=0.04,
            return_20d=0.08,
            volume_ratio=1.5,
        )

        self.assertFalse(stock_analyst.passes_filters(item, args))

    def test_reversal_setup_finds_put_after_spike(self):
        values = [100 + index * 0.2 for index in range(80)]
        values.extend([120, 123, 126, 129, 128])
        volumes = [1_000_000] * (len(values) - 1) + [1_400_000]
        series = stock_analyst.PriceSeries(
            symbol="TEST",
            dates=[],
            opens=[value - 0.5 for value in values],
            highs=[value + 1 for value in values],
            lows=[value - 1 for value in values],
            closes=values,
            volumes=volumes,
        )

        score, label, notes, direction = stock_analyst.score_reversal_setup(series)

        self.assertEqual(direction, "PUT")
        self.assertGreaterEqual(score, 50)
        self.assertTrue(label)
        self.assertTrue(notes)

    def test_trade_brief_creates_weighted_recommendation(self):
        item = stock_analyst.Analysis(
            symbol="TEST",
            name="Test Co",
            price=100,
            score=70,
            rating="Candidate",
            momentum_score=70,
            value_score=50,
            risk_score=60,
            yield_score=40,
            return_1y=0.12,
            return_6m=0.05,
            return_3m=0.03,
            volatility=0.3,
            max_drawdown=-0.12,
            sharpe_like=None,
            rsi=43,
            sma_50=98,
            sma_200=90,
            market_cap=None,
            pe=None,
            dividend_yield=None,
            beta=None,
            notes=[],
            news=[],
            setup_score=88,
            setup_label="A reversal",
            setup_notes=["near major 60-day support", "bullish candle rejection", "reversal volume present"],
            setup_direction="CALL",
            setup_strategy="reversal",
            return_1d=0.02,
            return_5d=-0.04,
            return_20d=-0.05,
            volume_ratio=1.4,
            chart_highs=[101 + index * 0.1 for index in range(60)],
            chart_lows=[96 + index * 0.04 for index in range(60)],
            chart_closes=[98 + index * 0.04 for index in range(60)],
            intraday_closes=[99 + index * 0.03 for index in range(30)],
            catalyst_score=70,
            catalyst_label="Catalyst support",
        )

        brief = stock_analyst.build_trade_brief(item, {"available": True, "bullish": True, "bearish": False, "label": "bullish/neutral tape"})
        item.trade_brief = brief

        self.assertGreater(brief.confidence_score, 0)
        self.assertTrue(brief.final_recommendation)
        self.assertIn("Bull case", brief.bull_case)
        self.assertTrue(brief.take_reasons)
        self.assertIsNotNone(brief.target_1)

        rationale = stock_analyst.professional_trade_rationale(item)
        self.assertIn("Analyst stance:", rationale)
        self.assertIn("What I like:", rationale)
        self.assertIn("What I dislike:", rationale)
        self.assertIn("Catalyst judgment:", rationale)
        self.assertIn("Trader judgment:", rationale)
        self.assertIn("Trade criticism:", rationale)
        self.assertIn("Execution plan:", rationale)
        self.assertIn("Do not chase the open", rationale)

        html = stock_analyst.secondary_analysis_html(item)
        self.assertIn("Professional Analyst Read", html)
        self.assertNotIn("Professional Read</strong>", html)

    def test_analyst_stance_does_not_auto_pass_low_rr(self):
        item = stock_analyst.Analysis(
            symbol="TEST",
            name="Test Co",
            price=100,
            score=70,
            rating="Candidate",
            momentum_score=70,
            value_score=50,
            risk_score=60,
            yield_score=40,
            return_1y=0.12,
            return_6m=0.05,
            return_3m=0.03,
            volatility=0.3,
            max_drawdown=-0.12,
            sharpe_like=None,
            rsi=43,
            sma_50=98,
            sma_200=90,
            market_cap=None,
            pe=None,
            dividend_yield=None,
            beta=None,
            notes=[],
            news=[],
            setup_score=88,
            setup_label="A reversal",
            setup_notes=["near major 60-day support", "bullish candle rejection"],
            setup_direction="CALL",
            setup_strategy="reversal",
            return_1d=0.02,
            return_5d=-0.04,
            return_20d=-0.05,
            volume_ratio=1.4,
            chart_highs=[101 + index * 0.1 for index in range(60)],
            chart_lows=[96 + index * 0.04 for index in range(60)],
            chart_closes=[98 + index * 0.04 for index in range(60)],
            catalyst_score=80,
            catalyst_label="Strong catalyst support",
        )

        brief = stock_analyst.build_trade_brief(item, {"available": True, "bullish": True, "bearish": False, "label": "bullish/neutral tape"})
        brief.risk_reward = 0.4

        self.assertEqual(stock_analyst.analyst_stance(item, brief), "Early watch - needs a better entry")

    def test_final_trade_candidate_requires_real_money_quality(self):
        item = stock_analyst.Analysis(
            symbol="TEST",
            name="Test Co",
            price=100,
            score=70,
            rating="Candidate",
            momentum_score=70,
            value_score=50,
            risk_score=60,
            yield_score=40,
            return_1y=0.12,
            return_6m=0.05,
            return_3m=0.03,
            volatility=0.3,
            max_drawdown=-0.12,
            sharpe_like=None,
            rsi=43,
            sma_50=98,
            sma_200=90,
            market_cap=None,
            pe=None,
            dividend_yield=None,
            beta=None,
            notes=[],
            news=[],
            setup_score=75,
            setup_label="A reversal",
            setup_notes=["near support"],
            setup_direction="PUT",
            setup_strategy="reversal",
            return_1d=0.02,
            return_5d=0.04,
            return_20d=0.05,
            volume_ratio=0.7,
            chart_highs=[101 + index * 0.1 for index in range(60)],
            chart_lows=[96 + index * 0.04 for index in range(60)],
            chart_closes=[98 + index * 0.04 for index in range(60)],
            catalyst_score=55,
            catalyst_label="Weak catalyst",
            option=stock_analyst.OptionContract(
                contract_symbol="TEST260626P00100000",
                side="PUT",
                strike=100,
                expiration=dt.date.today() + dt.timedelta(days=4),
                bid=1.0,
                ask=2.0,
                last_price=1.5,
                volume=10,
                open_interest=None,
                implied_volatility=None,
            ),
        )
        brief = stock_analyst.build_trade_brief(item, {"available": True, "bullish": False, "bearish": True, "label": "risk-off tape"})
        item.trade_brief = brief

        self.assertLess(stock_analyst.real_money_trader_judgment(item, brief)["score"], 62)
        self.assertFalse(stock_analyst.is_final_trade_candidate(item))

    def test_entry_status_confirms_when_trigger_quality_aligns(self):
        item = stock_analyst.Analysis(
            symbol="TEST",
            name="Test Co",
            price=100,
            score=80,
            rating="Candidate",
            momentum_score=75,
            value_score=55,
            risk_score=65,
            yield_score=40,
            return_1y=0.12,
            return_6m=0.06,
            return_3m=0.04,
            volatility=0.25,
            max_drawdown=-0.10,
            sharpe_like=None,
            rsi=55,
            sma_50=98,
            sma_200=92,
            market_cap=None,
            pe=None,
            dividend_yield=None,
            beta=None,
            notes=[],
            news=[],
            setup_score=86,
            setup_label="A reversal",
            setup_notes=["near major 60-day support", "bullish candle rejection"],
            setup_direction="CALL",
            setup_strategy="reversal",
            return_1d=0.02,
            return_5d=-0.02,
            return_20d=0.01,
            volume_ratio=1.4,
            chart_highs=[102 + index * 0.04 for index in range(60)],
            chart_lows=[96 + index * 0.03 for index in range(60)],
            chart_closes=[98 + index * 0.04 for index in range(60)],
            intraday_closes=[98 + index * 0.2 for index in range(30)],
            catalyst_score=82,
            catalyst_label="Strong catalyst support",
            option=stock_analyst.OptionContract(
                contract_symbol="TEST260626C00100000",
                side="CALL",
                strike=100,
                expiration=dt.date.today() + dt.timedelta(days=14),
                bid=1.0,
                ask=1.1,
                last_price=1.05,
                volume=1000,
                open_interest=None,
                implied_volatility=None,
            ),
        )
        brief = stock_analyst.build_trade_brief(item, {"available": True, "bullish": True, "bearish": False, "label": "bullish tape"})
        brief.risk_reward = 2.5

        status, detail = stock_analyst.entry_status(item, brief)

        self.assertEqual(status, "Confirmed entry")
        self.assertIn("aligned", detail)

    def test_entry_status_rejects_vetoed_trade(self):
        item = stock_analyst.Analysis(
            symbol="GOOGL",
            name="Alphabet",
            price=100,
            score=70,
            rating="Candidate",
            momentum_score=70,
            value_score=50,
            risk_score=60,
            yield_score=40,
            return_1y=0.12,
            return_6m=0.05,
            return_3m=0.03,
            volatility=0.3,
            max_drawdown=-0.12,
            sharpe_like=None,
            rsi=50,
            sma_50=98,
            sma_200=90,
            market_cap=None,
            pe=None,
            dividend_yield=None,
            beta=None,
            notes=[],
            news=[],
            macro_news=[stock_analyst.NewsItem("Oil jumps as Iran shuts Strait of Hormuz", "", "", "Reuters")],
            setup_score=75,
            setup_label="A reversal",
            setup_notes=["near support"],
            setup_direction="CALL",
            setup_strategy="reversal",
            return_1d=0.02,
            return_5d=-0.02,
            return_20d=0.01,
            volume_ratio=1.2,
            chart_highs=[102 + index * 0.04 for index in range(60)],
            chart_lows=[96 + index * 0.03 for index in range(60)],
            chart_closes=[98 + index * 0.04 for index in range(60)],
            intraday_closes=[98 + index * 0.2 for index in range(30)],
            catalyst_score=60,
            catalyst_label="Catalyst support",
        )
        brief = stock_analyst.build_trade_brief(item, {"available": True, "oil_shock": True, "label": "oil shock"})

        status, detail = stock_analyst.entry_status(item, brief)

        self.assertEqual(status, "Avoid / invalidated")
        self.assertIn("vetoed", detail)

    def test_alert_candidates_require_watch_to_entry_transition(self):
        item = stock_analyst.Analysis(
            symbol="TEST",
            name="Test Co",
            price=100,
            score=80,
            rating="Candidate",
            momentum_score=75,
            value_score=55,
            risk_score=65,
            yield_score=40,
            return_1y=0.12,
            return_6m=0.06,
            return_3m=0.04,
            volatility=0.25,
            max_drawdown=-0.10,
            sharpe_like=None,
            rsi=55,
            sma_50=98,
            sma_200=92,
            market_cap=None,
            pe=None,
            dividend_yield=None,
            beta=None,
            notes=[],
            news=[],
            setup_direction="CALL",
        )
        original_stance = stock_analyst.analyst_stance
        original_status = stock_analyst.entry_status
        try:
            stock_analyst.analyst_stance = lambda _item, _brief: "Actionable on trigger"
            stock_analyst.entry_status = lambda _item, _brief: ("Confirmed entry", "aligned")

            self.assertEqual(stock_analyst.alert_candidates_from_transitions([item], {}), [])

            prior = {
                "TEST:CALL": {
                    "symbol": "TEST",
                    "direction": "CALL",
                    "stance": "Watch only",
                    "status": "Trigger forming",
                }
            }
            candidates = stock_analyst.alert_candidates_from_transitions([item], prior)

            self.assertEqual(candidates, [(item, "Actionable on trigger", "Confirmed entry")])
        finally:
            stock_analyst.analyst_stance = original_stance
            stock_analyst.entry_status = original_status


if __name__ == "__main__":
    unittest.main()
