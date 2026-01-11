from datetime import date

from pydantic import BaseModel


class CashupDailyOut(BaseModel):
    date: date
    total_pence: int
    totals_by_method: dict[str, int]


class FinanceCashupOut(BaseModel):
    range: dict[str, date]
    totals_by_method: dict[str, int]
    total_pence: int
    daily: list[CashupDailyOut]


class FinanceOutstandingDebtorOut(BaseModel):
    patient_id: int
    patient_name: str
    balance_pence: int


class FinanceOutstandingOut(BaseModel):
    as_of: date
    total_outstanding_pence: int
    count_patients_with_balance: int
    top_debtors: list[FinanceOutstandingDebtorOut]


class FinanceTrendPointOut(BaseModel):
    date: date
    payments_pence: int
    charges_pence: int
    net_pence: int


class FinanceTrendsOut(BaseModel):
    days: int
    series: list[FinanceTrendPointOut]
