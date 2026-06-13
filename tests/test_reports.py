import pytest
from src.businesses import schemas


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
