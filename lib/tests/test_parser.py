"""Tests for bchydro_export.parser."""

from datetime import datetime
from pathlib import Path

from bchydro_export.parser import ConsumptionReading, parse_csv

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_csv_returns_valid_rows():
    csv_text = (FIXTURES / "consumption.csv").read_text()
    readings = parse_csv(csv_text)
    assert len(readings) == 4


def test_parse_csv_timestamps_are_naive_datetimes():
    csv_text = (FIXTURES / "consumption.csv").read_text()
    readings = parse_csv(csv_text)
    assert readings[0].timestamp == datetime(2026, 3, 1, 0, 0)
    assert readings[0].timestamp.tzinfo is None


def test_parse_csv_kwh_values():
    csv_text = (FIXTURES / "consumption.csv").read_text()
    readings = parse_csv(csv_text)
    assert readings[0].kwh == 0.45
    assert readings[1].kwh == 0.16
    assert readings[3].kwh == 1.23


def test_parse_csv_estimated_flag():
    csv_text = (FIXTURES / "consumption.csv").read_text()
    readings = parse_csv(csv_text)
    assert readings[0].estimated is False
    assert readings[1].estimated is False
    assert readings[2].estimated is True
    assert readings[3].estimated is False


def test_parse_csv_empty_string():
    readings = parse_csv("")
    assert readings == []


def test_parse_csv_header_only():
    csv_text = (FIXTURES / "consumption.csv").read_text()
    header = csv_text.splitlines()[0]
    readings = parse_csv(header)
    assert readings == []


def test_parse_csv_malformed_timestamp_skipped():
    csv_text = (
        '"Account Holder","Account Number","Meter Number","Interval Start Date/Time",'
        '"Time of Day Period","Inflow (kWh)","Outflow (kWh)","Net Consumption (kWh)",'
        '"Peak Demand (kW)","Power Factor (%)","Estimated Usage","Service Address","City"\n'
        '"TEST","\'000","\'123","BAD-TIMESTAMP","N/A","0.5","N/A","0.5","N/A","N/A","","X","Y"'
    )
    readings = parse_csv(csv_text)
    assert readings == []
