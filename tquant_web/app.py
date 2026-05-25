from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime
from typing import List

import pandas as pd
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    Response,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename

from tquant.data.akshare_provider import fetch_akshare_daily, fetch_akshare_minute
from tquant.config import ensure_project_dirs, load_config
from tquant.core.execution_plan import build_execution_plans
from tquant.io import load_watchlist, normalize_symbol
from tquant.trading.journal import append_trade, journal_summary, read_journal
from tquant.workflow import (
    build_data_status,
    generate_samples,
    latest_file,
    read_latest_csv,
    run_analyze,
    run_backtest,
    run_optimize,
    run_profile,
    save_watchlist_rows,
)
from tquant_web.viewmodels import build_stock_detail


def _display_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return df.fillna("")


def create_app(config_path: str = "config/settings.json") -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("TQUANT_SECRET_KEY", "tquant-local-dashboard")
    app.config["TQUANT_CONFIG_PATH"] = config_path

    @app.before_request
    def require_password():
        password = os.environ.get("TQUANT_PASSWORD", "")
        if not password:
            return None
        auth = request.authorization
        if auth and auth.password == password:
            return None
        return Response(
            "Authentication required",
            401,
            {"WWW-Authenticate": 'Basic realm="TQuant"'},
        )

    def cfg():
        config = load_config(app.config["TQUANT_CONFIG_PATH"])
        ensure_project_dirs(config)
        return config

    @app.template_filter("pct")
    def pct(value) -> str:
        try:
            return f"{float(value) * 100:.2f}%"
        except Exception:
            return "-"

    @app.template_filter("num")
    def num(value, digits=2) -> str:
        try:
            return f"{float(value):.{int(digits)}f}"
        except Exception:
            return "-"

    @app.context_processor
    def inject_globals():
        config = cfg()
        return {
            "cost_edge": config.costs.practical_edge_rate,
            "decision_time": config.signals.decision_time,
        }

    @app.get("/")
    def dashboard():
        config = cfg()
        signals = _display_df(read_latest_csv(config.data.output_dir, "signals_*.csv"))
        profiles = _display_df(read_latest_csv(config.data.output_dir, "stock_profiles_*.csv"))
        summary = _display_df(read_latest_csv(config.data.output_dir, "backtest_summary_*.csv"))
        by_symbol = _display_df(read_latest_csv(config.data.output_dir, "backtest_by_symbol_*.csv"))
        data_status = _display_df(build_data_status(config))
        plans = _display_df(build_execution_plans(config))

        market_breadth = {"score": 0, "sentiment": "非交易时段", "limit_up": 0, "limit_down": 0}
        try:
            from tquant.data.market_breadth import fetch_breadth_cached
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(fetch_breadth_cached)
                mb = future.result(timeout=5)
                if mb is not None:
                    market_breadth = {
                        "score": round(mb.breadth_score, 2),
                        "sentiment": mb.sentiment,
                        "limit_up": mb.limit_up_count,
                        "limit_down": mb.limit_down_count,
                    }
        except (FutureTimeoutError, Exception):
            pass

        # Also fetch real-time prices via Sina for the stock pool
        try:
            from tquant.data.sina_provider import fetch_realtime_batch
            items = load_watchlist(config.data.watchlist_path)
            symbols = [item.symbol for item in items]
            rt_df = fetch_realtime_batch(symbols)
            if not rt_df.empty:
                for _, row in rt_df.iterrows():
                    if "symbol" in row and "price" in row:
                        pass  # prices available via SSE
        except Exception:
            pass
        plan_active_count = 0
        if not plans.empty and "recommendation" in plans.columns:
            plan_active_count = int(
                plans["recommendation"].isin(["积极做T", "适度做T", "保守做T"]).sum()
            )
        data_ok_count = 0
        if not data_status.empty and "status" in data_status.columns:
            data_ok_count = int((data_status["status"] == "可用").sum())
        active = pd.DataFrame()
        holds = pd.DataFrame()
        if not signals.empty and "action" in signals.columns:
            active = signals[signals["action"] != "hold"].sort_values("score", ascending=False)
            holds = signals[signals["action"] == "hold"].sort_values("score", ascending=False)

        return render_template(
            "dashboard.html",
            signals=signals,
            active=active,
            holds=holds,
            profiles=profiles,
            summary=summary,
            by_symbol=by_symbol,
            data_status=data_status,
            plans=plans,
            plan_active_count=plan_active_count,
            data_ok_count=data_ok_count,
            market_breadth=market_breadth,
            latest_signal=latest_file(config.data.output_dir, "signals_*.csv"),
            latest_profile=latest_file(config.data.output_dir, "stock_profiles_*.csv"),
            latest_backtest=latest_file(config.data.output_dir, "backtest_report_*.md"),
        )

    @app.get("/stock/<symbol>")
    def stock_detail(symbol: str):
        config = cfg()
        try:
            detail = build_stock_detail(config, symbol)
        except Exception as exc:
            flash(f"无法打开股票详情：{exc}", "error")
            return redirect(url_for("dashboard"))
        return render_template("stock_detail.html", **detail)

    @app.get("/journal")
    def journal():
        config = cfg()
        df = _display_df(read_journal(config))
        if not df.empty and "date" in df.columns:
            df = df.sort_values("date", ascending=False)
        summary = journal_summary(df)
        try:
            items = load_watchlist(config.data.watchlist_path)
        except Exception:
            items = []
        return render_template("journal.html", trades=df, summary=summary, items=items)

    @app.post("/journal")
    def save_trade():
        config = cfg()
        try:
            append_trade(
                config,
                {
                    "date": request.form.get("date"),
                    "symbol": request.form.get("symbol"),
                    "name": request.form.get("name"),
                    "action": request.form.get("action"),
                    "quantity": request.form.get("quantity"),
                    "sell_price": request.form.get("sell_price"),
                    "buy_price": request.form.get("buy_price"),
                    "note": request.form.get("note"),
                },
            )
            flash("做T记录已保存。", "success")
        except Exception as exc:
            flash(f"保存失败：{exc}", "error")
        return redirect(url_for("journal"))

    @app.post("/refresh")
    def refresh():
        config = cfg()
        action = request.form.get("action", "all")
        try:
            if action == "sample":
                symbols = request.form.get("symbols", "000001,600519,300750").split(",")
                generate_samples(config, symbols)
                flash("样例数据已生成。", "success")
            if action in {"profile", "all"}:
                run_profile(config)
            if action in {"signals", "all"}:
                run_analyze(config)
            if action in {"backtest", "all"}:
                run_backtest(config)
            if action != "sample":
                flash("刷新完成。", "success")
        except Exception as exc:
            flash(f"刷新失败：{exc}", "error")
        return redirect(url_for("dashboard"))

    @app.get("/watchlist")
    def watchlist():
        config = cfg()
        try:
            items = load_watchlist(config.data.watchlist_path)
        except Exception:
            items = []
        return render_template("watchlist.html", items=items)

    @app.post("/watchlist")
    def save_watchlist():
        config = cfg()
        symbols = request.form.getlist("symbol")
        names = request.form.getlist("name")
        sectors = request.form.getlist("sector")
        positions = request.form.getlist("base_position")
        costs = request.form.getlist("avg_cost")
        rows: List[dict] = []
        for idx, symbol in enumerate(symbols):
            rows.append(
                {
                    "symbol": symbol,
                    "name": names[idx] if idx < len(names) else "",
                    "sector": sectors[idx] if idx < len(sectors) else "",
                    "base_position": positions[idx] if idx < len(positions) else 0,
                    "avg_cost": costs[idx] if idx < len(costs) else 0,
                }
            )
        save_watchlist_rows(config, rows)
        flash("股票池已保存。", "success")
        return redirect(url_for("watchlist"))

    @app.get("/data")
    def data_page():
        config = cfg()
        return render_template("data.html", data_status=_display_df(build_data_status(config)))

    @app.post("/data/upload")
    def upload_data():
        config = cfg()
        file = request.files.get("file")
        data_type = request.form.get("data_type", "daily")
        symbol = normalize_symbol(request.form.get("symbol", ""))
        if file is None or not file.filename:
            flash("请选择 CSV 文件。", "error")
            return redirect(url_for("data_page"))
        if not symbol.strip("0"):
            flash("请填写股票代码。", "error")
            return redirect(url_for("data_page"))
        filename = secure_filename(file.filename)
        if not filename.lower().endswith(".csv"):
            flash("只支持 CSV 文件。", "error")
            return redirect(url_for("data_page"))

        target_dir = {
            "daily": config.data.daily_dir,
            "minute": config.data.minute_dir,
            "index": config.data.index_daily_dir,
        }.get(data_type, config.data.daily_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        file.save(target_dir / f"{symbol}.csv")
        flash(f"{symbol} 数据已上传。", "success")
        return redirect(url_for("data_page"))

    @app.post("/data/fetch-akshare")
    def fetch_data():
        config = cfg()
        try:
            items = load_watchlist(config.data.watchlist_path)
            symbols = [item.symbol for item in items]
            if request.form.get("daily"):
                fetch_akshare_daily(
                    symbols,
                    config.data.daily_dir,
                    request.form.get("start_date", "20230101"),
                    request.form.get("end_date") or datetime.now().strftime("%Y%m%d"),
                )
            if request.form.get("minute"):
                fetch_akshare_minute(
                    symbols,
                    config.data.minute_dir,
                    period=request.form.get("period", "1"),
                )
            flash("AkShare 数据拉取完成。", "success")
        except Exception as exc:
            flash(f"AkShare 拉取失败：{exc}", "error")
        return redirect(url_for("data_page"))

    @app.get("/outputs")
    def outputs():
        config = cfg()
        files = sorted(
            [path for path in config.data.output_dir.glob("*") if path.is_file()],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        return render_template("outputs.html", files=files)

    @app.get("/outputs/<path:filename>")
    def output_file(filename: str):
        config = cfg()
        return send_from_directory(config.data.output_dir, filename, as_attachment=False)

    @app.get("/stream")
    def sse_stream():
        def event_stream():
            config = cfg()
            while True:
                try:
                    breadth_data = {"score": 0, "sentiment": "未知"}
                    try:
                        from tquant.data.market_breadth import fetch_breadth_cached
                        mb = fetch_breadth_cached()
                        if mb is not None:
                            breadth_data = {
                                "score": round(mb.breadth_score, 2),
                                "sentiment": mb.sentiment,
                                "limit_up": mb.limit_up_count,
                                "limit_down": mb.limit_down_count,
                            }
                    except Exception:
                        pass

                    # Real-time prices from mootdx
                    rt_prices = {}
                    try:
                        from tquant.data.stable_provider import fetch_realtime_quote
                        from tquant.io import load_watchlist
                        items = load_watchlist(config.data.watchlist_path)
                        for item in items:
                            rt = fetch_realtime_quote(item.symbol)
                            if rt and rt.get("price", 0) > 0:
                                rt_prices[item.symbol] = {
                                    "price": rt["price"],
                                    "change": round(float(rt.get("change", 0)), 4),
                                    "name": rt.get("name", item.name),
                                }
                    except Exception:
                        pass

                    plans = build_execution_plans(config)
                    plan_count = 0
                    if not plans.empty and "recommendation" in plans.columns:
                        plan_count = int(
                            plans["recommendation"].isin(["积极做T", "适度做T", "保守做T"]).sum()
                        )

                    now = datetime.now().strftime("%H:%M:%S")
                    yield f"data: {json.dumps({'time': now, 'breadth': breadth_data, 'plan_count': plan_count, 'prices': rt_prices})}\n\n"

                    hour_min = datetime.now().strftime("%H:%M")
                    if hour_min in ("10:30", "10:31", "14:00", "14:01", "14:45", "14:46"):
                        yield f"event: time_reminder\ndata: {json.dumps({'msg': f'{hour_min} 时间节点提醒', 'time': hour_min})}\n\n"

                    time.sleep(30)
                except GeneratorExit:
                    break
                except Exception:
                    time.sleep(30)

        return Response(
            event_stream(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    @app.get("/optimize")
    def optimize_page():
        config = cfg()
        suggestions_file = latest_file(config.data.output_dir, "optimization_*.csv")
        suggestions_df = pd.DataFrame()
        if suggestions_file:
            suggestions_df = _display_df(pd.read_csv(suggestions_file, dtype={"symbol": str}))
        report_file = latest_file(config.data.output_dir, "optimization_*.md")
        report_text = ""
        if report_file:
            report_text = report_file.read_text(encoding="utf-8")
        return render_template(
            "optimize.html",
            suggestions=suggestions_df,
            report=report_text,
            report_file=report_file,
        )

    @app.post("/optimize")
    def run_optimization():
        config = cfg()
        try:
            run_optimize(config)
            flash("参数优化完成。", "success")
        except Exception as exc:
            flash(f"优化失败：{exc}", "error")
        return redirect(url_for("optimize_page"))

    return app


app = create_app()


if __name__ == "__main__":
    import os as _os
    host = _os.environ.get("TQUANT_HOST", "0.0.0.0")
    port = int(_os.environ.get("TQUANT_PORT", "8000"))
    app.run(host=host, port=port, debug=False, use_reloader=False)
