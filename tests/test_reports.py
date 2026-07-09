import pytest
from src.analytics import schemas
from datetime import date, timedelta


def test_dashboard(authorized_user_client, authorized_user_client_cre_bus, test_create_sale_cli):
    business_id = authorized_user_client_cre_bus[0].business_id
    res = authorized_user_client.get(
        f"/reports/analytics/dashboard/{business_id}"
    )
    assert res.status_code == 200
    dash = schemas.DashboardResponse(**res.json())
    assert dash.total_revenue >= 0
    assert dash.total_profit >= 0
    assert dash.total_sales > 0
    assert dash.total_active_products > 0
    assert dash.total_customers >= 0
    assert dash.total_debt >= 0
    assert dash.best_selling_product != ""


def test_dashboard_unauthorized(client, authorized_user_client_cre_bus, test_create_sale_cli):
    business_id = authorized_user_client_cre_bus[0].business_id
    res = client.get(
        f"/reports/analytics/dashboard/{business_id}"
    )
    assert res.status_code == 401


def test_dashboard_response_structure(authorized_user_client, authorized_user_client_cre_bus, test_create_sale_cli):
    business_id = authorized_user_client_cre_bus[0].business_id
    res = authorized_user_client.get(
        f"/reports/analytics/dashboard/{business_id}"
    )
    assert res.status_code == 200
    data = res.json()

    assert data["total_revenue"] > 0
    assert data["total_profit"] > 0
    assert data["total_sales"] > 0
    assert data["sold_quantity"] > 0
    assert data["profit_margin"] > 0
    assert data["best_selling_product"] != "N/A"
    assert data["total_cost"] > 0
    assert data["low_stock_count"] > 0
    assert isinstance(data["low_stock_products"], list)
    assert data["total_active_products"] > 0
    assert data["start_date"] is None
    assert data["end_date"] is None


def test_dashboard_with_date_range(authorized_user_client, authorized_user_client_cre_bus, test_create_sale_cli):
    business_id = authorized_user_client_cre_bus[0].business_id
    last_week = (date.today() - timedelta(days=7)).isoformat()
    today = date.today().isoformat()

    res = authorized_user_client.get(
        f"/reports/analytics/dashboard/{business_id}?date={last_week}&end_date={today}"
    )
    assert res.status_code == 200
    dash = schemas.DashboardResponse(**res.json())
    assert dash.start_date == date.fromisoformat(last_week)
    assert dash.end_date == date.fromisoformat(today)
    assert dash.total_sales > 0


def test_dashboard_date_range_no_data(authorized_user_client, authorized_user_client_cre_bus, test_create_sale_cli):
    business_id = authorized_user_client_cre_bus[0].business_id
    res = authorized_user_client.get(
        f"/reports/analytics/dashboard/{business_id}?date=2021-01-01&end_date=2021-01-31"
    )
    assert res.status_code == 200
    dash = schemas.DashboardResponse(**res.json())
    assert dash.total_sales == 0
    assert dash.total_revenue == 0
    assert dash.total_profit == 0
    assert dash.sold_quantity == 0
    assert dash.best_selling_product == "N/A"


def test_dashboard_future_dates(authorized_user_client, authorized_user_client_cre_bus, test_create_sale_cli):
    business_id = authorized_user_client_cre_bus[0].business_id
    future = "2099-12-01"
    res = authorized_user_client.get(
        f"/reports/analytics/dashboard/{business_id}?date={future}&end_date=2099-12-31"
    )
    assert res.status_code == 400


def test_dashboard_end_before_start(authorized_user_client, authorized_user_client_cre_bus, test_create_sale_cli):
    business_id = authorized_user_client_cre_bus[0].business_id
    res = authorized_user_client.get(
        f"/reports/analytics/dashboard/{business_id}?date=2026-06-10&end_date=2026-06-05"
    )
    assert res.status_code == 400


def test_dashboard_forbidden_business(authorized_user_client, authorized_user_client_cre_bus, test_create_sale_cli):
    wrong_business_id = 9999
    res = authorized_user_client.get(
        f"/reports/analytics/dashboard/{wrong_business_id}"
    )
    assert res.status_code == 403


def test_daily_sales_report(authorized_user_client, authorized_user_client_cre_bus, test_create_sale_cli):
    res = authorized_user_client.post(
        "/admin/crons/daily_summery"
    )
    assert res.status_code == 200
    
def test_weekly_sales_report(authorized_user_client, authorized_user_client_cre_bus, test_create_sale_cli):
    res = authorized_user_client.post(
        "/admin/crons/weekly_summery"
    )
    assert res.status_code == 200
    
def test_monthly_sales_report(authorized_user_client, authorized_user_client_cre_bus, test_create_sale_cli):
    res = authorized_user_client.post(
        "/admin/crons/monthly_summery"
    )
    assert res.status_code == 200

def test_monthly_sales_report_unauthroized(client, authorized_user_client_cre_bus, test_create_sale_cli):
    res = client.post(
        "/admin/crons/monthly_summery"
    )
    assert res.status_code == 401

def test_list_jobs(authorized_user_client, authorized_user_client_cre_bus, test_create_sale_cli):
    res = authorized_user_client.get(
        "/admin/crons/jobs"
    )
    assert res.status_code == 200
    
def test_reports_profit(authorized_user_client, authorized_user_client_cre_bus, test_create_sale_cli):
    res = authorized_user_client.get(
        f"/reports/profit/{authorized_user_client_cre_bus[0].business_id}?date=2026-05-16&end_date=2026-05-17"
    )
    print(res.json())
    assert res.status_code == 200
    profit = schemas.ProfitResponse(**res.json())
    print(profit.revenue)
    
def test_reports_profit_404(authorized_user_client, authorized_user_client_cre_bus, test_create_sale_cli):
    res = authorized_user_client.get(
        "/reports/profit?date=2026-05-14&end_date=2026-05-15"
    )
    assert res.status_code == 404


def test_get_summmery(authorized_user_client, authorized_user_client_cre_bus, test_create_sale_cli):
    res = authorized_user_client.get(
        f"/reports/analytics/summery/{authorized_user_client_cre_bus[0].business_id}?date=2026-05-18&end_date=2026-05-19"
    )

    assert res.status_code == 200
    summery = schemas.SaleSummery(**res.json())
    print(summery.total_revenue)
